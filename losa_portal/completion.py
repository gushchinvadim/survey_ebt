"""Review missing observations, atomically complete a sheet, or reopen it."""
import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from django.core import signing
from django.db import models, transaction
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from rest_framework import serializers

from losa.models import AuditSheet, FinalMarkCrew, DescentApproach, Landing, RolloutAndTaxingAndParking
from . import demography, approach, final_crew, observations, stage_assessments
from .access import can_start, can_view, portal_required
from .views import read_json

TOKEN_SALT = "losa-completion-review-v1"


class CompletionRequest(serializers.Serializer):
    form = serializers.DictField()
    scratch_count = serializers.IntegerField(min_value=0)
    review_token = serializers.CharField(required=False, allow_blank=True)
    acknowledge_missing = serializers.BooleanField(default=False)

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError("Переданы неизвестные поля завершения.")
        return super().to_internal_value(data)


def canonical(value):
    if isinstance(value, models.Model):
        return value.pk
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, (date, Decimal, UUID)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(canonical(value), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def missing(value):
    return value is None or (isinstance(value, str) and not value.strip())


def review_warnings(sheet, values):
    warnings = []
    def add(group, items):
        if items:
            warnings.append({"group": group, "items": items})

    basic = {
        "captain_experience": "КВС: общий стаж",
        "captain_type_experience": "КВС: стаж на типе",
        "first_officer_experience": "Второй пилот: общий стаж",
        "first_officer_type_experience": "Второй пилот: стаж на типе",
        "actual_departure": "Фактический аэропорт вылета",
        "actual_arrival": "Фактический аэропорт прилёта",
        "working_together": "Совместная работа экипажа",
        "pilot_flying": "Активное управление",
        "leg_number": "Участок полётного задания",
    }
    items = [label for field, label in basic.items() if missing(values.get(field, getattr(sheet, field)))]
    if values.get("is_delay", sheet.is_delay) and missing(values.get("delay", sheet.delay)):
        items.append("Продолжительность задержки")
    add("Общие данные", items)

    bundle = stage_assessments.bundle(sheet)
    for code, _ in stage_assessments.STAGES:
        definition = bundle["catalog"][code]
        block = values.get("stage_assessments", {}).get(code, bundle["form"][code])
        items = []
        if missing(block["facts"]):
            items.append("Изложение фактов")
        if not definition["configured"]:
            items.append("Шаблон критериев не настроен в админке")
        elif not any(section["criteria"] for section in definition["sections"]):
            items.append("В шаблоне ещё нет критериев")
        for section in definition["sections"]:
            for criterion in section["criteria"]:
                key = str(criterion["id"])
                score = block["scores"].get(key, bundle["form"][code]["scores"].get(key))
                if score is None:
                    items.append(f'{section["name"]}: {criterion["code"]} — {criterion["name"]}')
        add(definition["name"], items)

    descent = values.get("approach", approach.read(sheet))
    items = [
        str(DescentApproach._meta.get_field(field).verbose_name)
        for field in approach.DESCENT_FIELDS if field != "describe_deviation" and missing(descent["descent"][field])
    ]
    if descent["descent"]["descent_trajectory"] in ("2", "3") and missing(descent["descent"]["describe_deviation"]):
        items.append("Причина отклонения от траектории и действия экипажа")
    for field, label in (("approach_type", "Тип захода"), ("visual_condition", "Погодные условия")):
        if missing(descent["conditions"][field]):
            items.append(label)
    add("Снижение и условия захода", items)
    from losa.models import StabilizedApproachAssessment
    for code, label in StabilizedApproachAssessment.STAGE_CHOICES:
        row = descent["measurements"][code]
        fields = {
            "speed_deviation": "Отклонение скорости",
            "rate_of_descent_deviation": "Вертикальная скорость",
            "thrust_settings": "Режим двигателей",
            "landing_config": "Посадочная конфигурация",
            "course_deviation": "Отклонение по курсу",
            "glideslope_deviation": "Отклонение от глиссады",
        }
        add(label, [text for field, text in fields.items() if missing(row[field])])
    add("Посадка", [
        str(Landing._meta.get_field(field).verbose_name)
        for field in approach.LANDING_FIELDS if missing(descent["landing"][field])
    ])
    add("Пробег, руление и стоянка", [
        str(RolloutAndTaxingAndParking._meta.get_field(field).verbose_name)
        for field in approach.ROLLOUT_FIELDS
        if missing(descent["rollout"][field])
        and not (field == "thrust_reverser_off" and descent["rollout"]["thrust_reverser_on"] == "4")
    ])

    final = values.get("final_crew_mark", final_crew.read(sheet))
    add("Итоговая оценка", [
        str(FinalMarkCrew._meta.get_field(field).verbose_name)
        for field in final_crew.FIELDS if missing(final[field])
    ])

    existing = observations.read(sheet)
    journal = values.get("observations", {})
    for key, fields in (
        ("mistakes", {"who_made": "кто допустил", "who_noticed": "кто заметил",
                      "reaction": "реакция", "error_result": "результат", "is_action_ok": "удачны ли действия"}),
        ("threats", {"was_control_effective": "эффективность контроля", "correct_actions": "правильность действий"}),
    ):
        rows = {str(row["id"]): row for row in existing[key]}
        rows.update({str(row["id"]): row for row in journal.get(key, [])})
        for key_id in journal.get(f"deleted_{key}", []):
            rows.pop(str(key_id), None)
        items = []
        for index, row in enumerate(rows.values(), 1):
            gaps = [label for field, label in fields.items() if missing(row[field])]
            if key == "mistakes" and row["error_result"] == "2" and not row["safety_condition_ids"]:
                gaps.append("связь с изменением состояния безопасности")
            if gaps:
                items.append(f'{"Ошибка" if key == "mistakes" else "Угроза"} {index}: {", ".join(gaps)}')
        add("Контроль ошибок" if key == "mistakes" else "Контроль факторов угрозы", items)
    return warnings


def parse(request):
    serializer = CompletionRequest(data=read_json(request))
    if not serializer.is_valid():
        return None, None, JsonResponse({"detail": "Проверьте запрос завершения.", "errors": serializer.errors}, status=400)
    options = serializer.validated_data
    values, error = demography.deserialize_values(options["form"])
    if error is None and "stage_assessments" not in values:
        error = JsonResponse({"detail": "Для завершения обновите форму: нужны данные всех этапов в новом формате."}, status=400)
    return values, options, error


def context(request, pk):
    assignment = demography.locked_assignment(request.user, pk)
    if not can_view(assignment, request.user) or not assignment.audit_sheet_id:
        return None, None, JsonResponse({"detail": "Нет доступа к этой проверке."}, status=403)
    sheet = AuditSheet.objects.select_for_update().get(pk=assignment.audit_sheet_id)
    assignment.audit_sheet = sheet
    return assignment, sheet, None


def precheck(assignment, sheet, values, options):
    if options["scratch_count"]:
        return JsonResponse({"detail": "Есть незафиксированные наброски наблюдений. Зафиксируйте или удалите их перед завершением."}, status=400)
    if assignment.status != "scheduled":
        return JsonResponse({"detail": "Проверка уже завершена. Для исправлений верните её в работу."}, status=409)
    if sheet.demography_revision != values["revision"]:
        return JsonResponse({"detail": "На сервере другая версия листа. Обновите данные перед завершением."}, status=409)
    return demography.validate_values_for_sheet(sheet, values)


def review_identity(request, assignment, values, warnings):
    return {
        "user": request.user.pk,
        "assignment": str(assignment.pk),
        "revision": values["revision"],
        "form": digest(values),
        "warnings": digest(warnings),
    }


@never_cache
@require_POST
@csrf_protect
@portal_required
def preview_completion(request, pk):
    values, options, error = parse(request)
    if error is not None:
        return error
    with transaction.atomic():
        assignment, sheet, error = context(request, pk)
        if error is not None:
            return error
        error = precheck(assignment, sheet, values, options)
        if error is not None:
            return error
        warnings = review_warnings(sheet, values)
        return JsonResponse({
            "warnings": warnings,
            "missing_count": sum(len(group["items"]) for group in warnings),
            "review_token": signing.dumps(review_identity(request, assignment, values, warnings), salt=TOKEN_SALT),
        })


@never_cache
@require_POST
@csrf_protect
@portal_required
def complete_assignment(request, pk):
    values, options, error = parse(request)
    if error is not None:
        return error
    with transaction.atomic():
        assignment, sheet, error = context(request, pk)
        if error is not None:
            return error
        # A lost response can be retried after completion without another write.
        if assignment.status == "completed":
            if not options["scratch_count"] and demography.values_match(sheet, values):
                return JsonResponse(demography.response_payload(assignment))
            return JsonResponse({"detail": "Проверка завершена, но отправленные данные отличаются. Обновите лист."}, status=409)
        error = precheck(assignment, sheet, values, options)
        if error is not None:
            return error
        warnings = review_warnings(sheet, values)
        try:
            token = signing.loads(options.get("review_token", ""), salt=TOKEN_SALT, max_age=1800)
        except signing.BadSignature:
            return JsonResponse({"detail": "Проверка пропусков устарела. Выполните её ещё раз."}, status=409)
        if token != review_identity(request, assignment, values, warnings):
            return JsonResponse({"detail": "Данные или перечень пропусков изменились. Проверьте завершение ещё раз."}, status=409)
        if warnings and not options["acknowledge_missing"]:
            return JsonResponse({"detail": "Подтвердите завершение с перечисленными пропусками."}, status=400)
        result = demography.apply_locked_values(assignment, values)
        if result.status_code != 200:
            return result
        assignment.status = "completed"
        assignment.save(update_fields=["status"])
        return JsonResponse(demography.response_payload(assignment))


@never_cache
@require_POST
@csrf_protect
@portal_required
def reopen_assignment(request, pk):
    data = read_json(request)
    if not isinstance(data, dict) or set(data) != {"revision"} or type(data["revision"]) is not int or data["revision"] < 0:
        return JsonResponse({"detail": "Укажите версию листа."}, status=400)
    with transaction.atomic():
        assignment, sheet, error = context(request, pk)
        if error is not None:
            return error
        if assignment.status == "scheduled":
            if sheet.demography_revision == data["revision"] + 1:
                return JsonResponse(demography.response_payload(assignment))
            return JsonResponse({"detail": "Проверка уже в работе. Обновите лист."}, status=409)
        if sheet.demography_revision != data["revision"]:
            return JsonResponse({"detail": "На сервере другая версия. Обновите лист."}, status=409)
        assignment.status = "scheduled"
        assignment.save(update_fields=["status"])
        sheet.demography_revision += 1
        sheet.save(update_fields=["demography_revision"])
        return JsonResponse(demography.response_payload(assignment))
