"""Read-only analytics over saved portal audit sheets; no pilot identities returned."""
from collections import defaultdict
from datetime import date
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from losa.models import (AuditSheet, AuditThreat, AuditMistake, AuditCriterionRating,
                         AuditAssessment, FinalMarkCrew, AssessmentStage, AssessmentCriterion)
from .access import portal_required, roles_for


def coordinator_required(view):
    @wraps(view)
    @portal_required
    def wrapped(request, *args, **kwargs):
        if "coordinator" not in roles_for(request.user):
            return JsonResponse({"detail": "Аналитика доступна координатору программы."}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


def group_rows(rows, key):
    """Event count and distinct sheet count have intentionally different denominators."""
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[key]].append(row)
    return [dict(label=label, count=len(items), sheets=len({r['sheet_id'] for r in items}))
            for label, items in sorted(grouped.items(), key=lambda x: (-len(x[1]), str(x[0])))]


def yes_no(value):
    return "Не указано" if value is None else ("Да" if value else "Нет")


@never_cache
@require_GET
@coordinator_required
def analytics_view(request):
    status = request.GET.get("status", "completed")
    if status not in {"completed", "draft", "all"}:
        return JsonResponse({"detail": "Неизвестный статус."}, status=400)
    bounds = {}
    for key in ("from", "to"):
        raw = request.GET.get(key, "")
        if raw:
            try:
                bounds[key] = date.fromisoformat(raw)
            except ValueError:
                return JsonResponse({"detail": "Дата должна иметь формат ГГГГ-ММ-ДД."}, status=400)
    if bounds.get("from", date.min) > bounds.get("to", date.max):
        return JsonResponse({"detail": "Начало периода позже окончания."}, status=400)
    # Unassigned legacy sheets have no completion state, so must not silently join completed audits.
    base = AuditSheet.objects.filter(portal_assignment__isnull=False)
    options = list(base.values("aircraft_id", "aircraft__aircraft_type").distinct().order_by("aircraft__aircraft_type"))
    sheets = base.select_related("portal_assignment", "aircraft", "departure", "arrival")
    if status != "all":
        sheets = sheets.filter(portal_assignment__status="completed") if status == "completed" else sheets.exclude(portal_assignment__status="completed")
    if "from" in bounds:
        sheets = sheets.filter(date__gte=bounds["from"])
    if "to" in bounds:
        sheets = sheets.filter(date__lte=bounds["to"])
    aircraft = request.GET.get("aircraft", "")
    if aircraft:
        if not aircraft.isdecimal() or len(aircraft) > 18:
            return JsonResponse({"detail": "Некорректный тип ВС."}, status=400)
        sheets = sheets.filter(aircraft_id=int(aircraft))
    route = request.GET.get("route", "").strip().upper()
    sheet_rows = []
    for s in sheets.order_by("date", "pk"):
        departure = s.actual_departure or s.departure.airport_code
        arrival = s.actual_arrival or s.arrival.airport_code
        route_label = f"{departure} → {arrival}"
        sheet_rows.append({"id": s.pk, "sheet_id": s.pk, "number": s.audit_number,
                           "date": s.date.isoformat(), "aircraft": s.aircraft.aircraft_type,
                           "route": route_label, "status": s.portal_assignment.status,
                           "pilot_flying": s.get_pilot_flying_display() or "Не указано"})
    route_options = sorted({s["route"] for s in sheet_rows})
    if route:
        sheet_rows = [s for s in sheet_rows if s["route"].upper() == route]
    meta = {s["id"]: s for s in sheet_rows}
    ids = list(meta)
    threats = []
    for t in AuditThreat.objects.filter(audit_sheet_id__in=ids).select_related("threat", "flight_phase").order_by("pk"):
        threats.append({"id": t.pk, "sheet_id": t.audit_sheet_id,
                        "label": f"{t.threat.code} — {t.threat.describe}",
                        "category": t.threat.get_type_display(), "phase": str(t.flight_phase),
                        "effective": yes_no(t.was_control_effective), "correct": yes_no(t.correct_actions),
                        "comment": t.comment})
    threat_lookup = {t["id"]: t for t in threats}
    errors = []
    for e in AuditMistake.objects.filter(audit_sheet_id__in=ids).select_related("mistake__type", "flight_phase", "code_csc").order_by("pk"):
        linked = threat_lookup.get(e.for_threat_reason_id)
        errors.append({"id": e.pk, "sheet_id": e.audit_sheet_id,
                       "label": f"{e.mistake.code} — {e.mistake.name}",
                       "category": str(e.mistake.type), "phase": str(e.flight_phase),
                       "who_made": e.get_who_made_display() or "Не указано",
                       "noticed": e.get_who_noticed_display() or "Не указано",
                       "reaction": e.get_reaction_display() or "Не указано",
                       "result": e.get_error_result_display() or "Не указано",
                       "successful": yes_no(e.is_action_ok),
                       "threat": linked["label"] if linked and linked["sheet_id"] == e.audit_sheet_id else "Не указано",
                       "condition": str(e.code_csc) if e.code_csc_id else "Не указано",
                       "comment": e.comment})
    facts = {(a.audit_sheet_id, a.stage_id): a.facts for a in AuditAssessment.objects.filter(audit_sheet_id__in=ids)}
    ratings = []
    for r in AuditCriterionRating.objects.filter(audit_sheet_id__in=ids).select_related("stage", "criterion__section__template"):
        ratings.append({"sheet_id": r.audit_sheet_id, "stage": r.stage.name,
                        "stage_id": r.stage_id, "criterion_id": r.criterion_id,
                        "label": f"{r.criterion.code} — {r.criterion.name}",
                        "template": r.criterion.section.template.version, "score": r.score,
                        "comment": r.comment, "facts": facts.get((r.audit_sheet_id, r.stage_id), "")})
    final_fields = ("free_communication", "capt_as_leader", "general_mark_capt", "general_mark_copilot", "total_general_mark")
    for f in FinalMarkCrew.objects.filter(audit_sheet_id__in=ids):
        for field in final_fields:
            ratings.append({"sheet_id": f.audit_sheet_id, "stage": "Итоговая оценка",
                            "stage_id": "final", "criterion_id": field,
                            "label": str(FinalMarkCrew._meta.get_field(field).verbose_name),
                            "template": "Итог", "score": getattr(f, field),
                            "comment": "", "facts": f.general_notes})
    groups = {}
    for r in ratings:
        key = f"{r['stage_id']}:{r['criterion_id']}"
        group = groups.setdefault(key, {"key": key, "label": r["label"], "stage": r["stage"],
                                      "template": r["template"], "scores": [0, 0, 0, 0],
                                      "missing_saved": 0, "sheet_ids": set()})
        group["sheet_ids"].add(r["sheet_id"])
        if r["score"] in (1, 2, 3, 4):
            group["scores"][r["score"] - 1] += 1
        else:
            group["missing_saved"] += 1
        r["key"] = key
    for g in groups.values():
        g["sheets"] = len(g.pop("sheet_ids"))
    configured_templates = set(AssessmentCriterion.objects.values_list("section__template_id", flat=True))
    unconfigured = [s.name for s in AssessmentStage.objects.all() if s.template_id not in configured_templates]
    return JsonResponse({
        "sheets": sheet_rows, "threats": threats, "errors": errors, "ratings": ratings,
        "rating_groups": list(groups.values()),
        "summary": {"sheets": len(ids), "threats": len(threats), "errors": len(errors),
                    "sheets_with_threats": len({t['sheet_id'] for t in threats}),
                    "sheets_with_errors": len({e['sheet_id'] for e in errors}),
                    "scores": sum(r['score'] in (1, 2, 3, 4) for r in ratings)},
        "groups": {"aircraft": group_rows(sheet_rows, "aircraft"), "routes": group_rows(sheet_rows, "route"),
                   "threat_codes": group_rows(threats, "label"), "threat_categories": group_rows(threats, "category"),
                   "threat_phases": group_rows(threats, "phase"), "effective": group_rows(threats, "effective"),
                   "correct": group_rows(threats, "correct"), "error_codes": group_rows(errors, "label"),
                   "error_categories": group_rows(errors, "category"), "error_phases": group_rows(errors, "phase"),
                   "noticed": group_rows(errors, "noticed"), "reaction": group_rows(errors, "reaction"),
                   "result": group_rows(errors, "result"), "successful": group_rows(errors, "successful")},
        "options": {"aircraft": [{"id": o['aircraft_id'], "label": o['aircraft__aircraft_type']} for o in options], "routes": route_options},
        "quality": {"stages_without_criteria": unconfigured,
                    "unassigned_sheets": AuditSheet.objects.filter(portal_assignment__isnull=True).count()},
    })
