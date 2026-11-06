from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST, require_http_methods
from rest_framework import serializers

from losa.models import AuditSheet, Airport, Pilot
from .access import can_start, can_view, portal_required, visible_assignments
from .models import AuditAssignment
from . import preflight, cruise, approach, final_crew, observations, stage_assessments

EXPERIENCE_FIELDS = (
    "captain_experience",
    "captain_type_experience",
    "first_officer_experience",
    "first_officer_type_experience",
)
EDITABLE_FIELDS = (
    "date",
    "actual_departure",
    "actual_arrival",
    *EXPERIENCE_FIELDS,
    "working_together",
    "pilot_flying",
    "leg_number",
    "is_delay",
    "delay",
)


class DemographySerializer(serializers.Serializer):
    preflight = preflight.PreflightSerializer(required=False)
    cruise = cruise.CruiseSerializer(required=False)
    approach = approach.ApproachSerializer(required=False)
    final_crew_mark = final_crew.FinalCrewSerializer(required=False)
    observations = observations.JournalSerializer(required=False)
    stage_assessments = stage_assessments.StageAssessmentsSerializer(required=False)
    revision = serializers.IntegerField(min_value=0, required=True)
    date = serializers.DateField()
    actual_departure = serializers.CharField(max_length=100, allow_blank=True)
    actual_arrival = serializers.CharField(max_length=100, allow_blank=True)
    captain_experience = serializers.IntegerField(
        min_value=0, max_value=2147483647, allow_null=True
    )
    captain_type_experience = serializers.IntegerField(
        min_value=0, max_value=2147483647, allow_null=True
    )
    first_officer_experience = serializers.IntegerField(
        min_value=0, max_value=2147483647, allow_null=True
    )
    first_officer_type_experience = serializers.IntegerField(
        min_value=0, max_value=2147483647, allow_null=True
    )
    working_together = serializers.ChoiceField(
        choices=AuditSheet.WORKING_TOGETHER_CHOICE, allow_blank=True
    )
    pilot_flying = serializers.ChoiceField(
        choices=AuditSheet.PF_CHOICE, allow_blank=True, allow_null=True, required=False
    )
    leg_number = serializers.ChoiceField(
        choices=AuditSheet.LEG_NUMBER_CHOICE, allow_blank=True, allow_null=True, required=False
    )
    is_delay = serializers.BooleanField()
    delay = serializers.IntegerField(min_value=1, max_value=2147483647, allow_null=True)

    def validate(self, attrs):
        for total, on_type in (
            ("captain_experience", "captain_type_experience"),
            ("first_officer_experience", "first_officer_type_experience"),
        ):
            if (
                attrs[total] is not None
                and attrs[on_type] is not None
                and attrs[on_type] > attrs[total]
            ):
                raise serializers.ValidationError(
                    {on_type: "Стаж на типе не может превышать общий стаж."}
                )
        if not attrs["is_delay"]:
            attrs["delay"] = None
        return attrs


def response_payload(assignment):
    sheet = assignment.audit_sheet
    form = {field: getattr(sheet, field) for field in EDITABLE_FIELDS}
    form["date"] = sheet.date.isoformat()
    form["preflight"] = preflight.read(sheet)
    form["cruise"] = cruise.read(sheet)
    form["approach"] = approach.read(sheet)
    form["final_crew_mark"] = final_crew.read(sheet)
    form["observations"] = observations.read(sheet)
    stages = stage_assessments.bundle(sheet)
    form["stage_assessments"] = stages["form"]
    return {
        "assignment_id": str(assignment.pk),
        "status": assignment.status,
        "audit_number": sheet.audit_number,
        "revision": sheet.demography_revision,
        "form": form,
        "meta": {
            "preflight": preflight.catalog(),
            "approach": approach.catalog(),
            "final_crew_mark": final_crew.catalog(),
            "observations": observations.catalog(sheet),
            "stage_assessments": stages["catalog"],
            "planned_date": assignment.date.isoformat(),
            "flight_number": assignment.flight.number,
            "planned_departure": assignment.flight.departure.airport_code,
            "planned_arrival": assignment.flight.arrival.airport_code,
            "aircraft": assignment.flight.aircraft.aircraft_type,
            "captain_label": str(assignment.captain),
            "officer_label": str(assignment.first_officer),
            "leg_number_choices": list(AuditSheet.LEG_NUMBER_CHOICE),
            "pilot_flying_choices": list(AuditSheet.PF_CHOICE),
            "working_together_choices": list(AuditSheet.WORKING_TOGETHER_CHOICE),
            "airports": list(
                Airport.objects.order_by("airport_code").values(
                    "airport_code", "airport_name"
                )
            ),
        },
    }


def locked_assignment(user, pk):
    # No joined nullable relations in SELECT FOR UPDATE (important for PostgreSQL).
    visible = visible_assignments(user).filter(pk=pk).values_list("pk", flat=True)
    return get_object_or_404(
        AuditAssignment.objects.select_for_update(), pk__in=visible, pk=pk
    )


@never_cache
@require_POST
@csrf_protect
@portal_required
def open_demography(request, pk):
    with transaction.atomic():
        assignment = locked_assignment(request.user, pk)
        if assignment.status == "completed":
            if not can_view(assignment, request.user):
                return JsonResponse({"detail": "Нет доступа к завершённой проверке."}, status=403)
            return JsonResponse(response_payload(assignment))
        if not can_start(assignment, request.user):
            return JsonResponse(
                {
                    "detail": "Открыть форму может назначенный аудитор с назначенной даты и позже, пока проверка не завершена."
                },
                status=403,
            )
        if assignment.number is None:
            assignment.save(update_fields=["number"])
        if assignment.audit_sheet_id is None:
            # Draft: required-on-completion fields may remain empty for now.
            sheet = AuditSheet.objects.create(
                audit_number=assignment.audit_number,
                date=assignment.date,
                auditor=assignment.auditor,
                aircraft=assignment.flight.aircraft,
                captain=assignment.captain,
                first_officer=assignment.first_officer,
                departure=assignment.flight.departure,
                arrival=assignment.flight.arrival,
                actual_departure=assignment.flight.departure.airport_code,
                actual_arrival=assignment.flight.arrival.airport_code,
                captain_experience=assignment.captain.experience,
                captain_type_experience=assignment.captain.type_experience,
                first_officer_experience=assignment.first_officer.experience,
                first_officer_type_experience=assignment.first_officer.type_experience,
                working_together="",
            )
            assignment.audit_sheet = sheet
        if assignment.opened_at is None:
            assignment.opened_at = timezone.now()
        assignment.save(update_fields=["audit_sheet", "opened_at"])
        return JsonResponse(response_payload(assignment))


def deserialize_values(data):
    if not isinstance(data, dict):
        return None, JsonResponse({"detail": "Ожидается JSON-объект."}, status=400)
    allowed = set(EDITABLE_FIELDS) | {
        "revision", "preflight", "cruise", "approach",
        "final_crew_mark", "observations", "stage_assessments",
    }
    if set(data) - allowed:
        return None, JsonResponse({"detail": "Переданы поля, недоступные для изменения в этом блоке."}, status=400)
    serializer = DemographySerializer(data=data)
    if not serializer.is_valid():
        return None, JsonResponse({"detail": "Проверьте поля формы.", "errors": serializer.errors}, status=400)
    return serializer.validated_data, None


def values_match(sheet, values):
    return (
        all(getattr(sheet, f) == values.get(f, getattr(sheet, f)) for f in EDITABLE_FIELDS)
        and ("preflight" not in values or values["preflight"] == preflight.read(sheet))
        and ("cruise" not in values or values["cruise"] == cruise.read(sheet))
        and ("approach" not in values or approach.same_as_stored(sheet, values["approach"]))
        and ("final_crew_mark" not in values or values["final_crew_mark"] == final_crew.read(sheet))
        and ("observations" not in values or observations.same_as_stored(sheet, values["observations"]))
        and ("stage_assessments" not in values or stage_assessments.same_as_stored(sheet, values["stage_assessments"]))
    )


def validate_values_for_sheet(sheet, values):
    if "preflight" in values:
        try:
            preflight.definitions()
        except serializers.ValidationError as exc:
            return JsonResponse({"detail": str(exc.detail[0])}, status=400)
    if "cruise" in values:
        try:
            cruise.stage()
        except serializers.ValidationError as exc:
            return JsonResponse({"detail": str(exc.detail[0])}, status=400)
    if "observations" in values:
        try:
            observations.validate_for_sheet(sheet, values["observations"])
        except serializers.ValidationError as exc:
            return JsonResponse({"detail": "Проверьте связи наблюдений.", "errors": exc.detail}, status=400)
    if "stage_assessments" in values:
        if "preflight" in values or "cruise" in values:
            return JsonResponse({"detail": "Обновите фронтенд: оценки этапов переданы одновременно в старом и новом формате."}, status=400)
        try:
            stage_assessments.validate_for_sheet(sheet, values["stage_assessments"])
        except serializers.ValidationError as exc:
            return JsonResponse({"detail": "Проверьте критерии этапов.", "errors": exc.detail}, status=400)
    return None


def apply_locked_values(assignment, values):
    """Called only within a transaction holding the assignment lock."""
    sheet = AuditSheet.objects.select_for_update().get(pk=assignment.audit_sheet_id)
    if sheet.demography_revision != values["revision"]:
        # Repeated delivery of exactly the same payload is safe.
        if values_match(sheet, values):
            assignment.audit_sheet = sheet
            return JsonResponse(response_payload(assignment))
        return JsonResponse(
            {
                "detail": "На сервере уже есть другая версия. Локальный черновик сохранён. Загрузите серверный вариант или проверьте изменения.",
                "revision": sheet.demography_revision,
            },
            status=409,
        )
    validation_error = validate_values_for_sheet(sheet, values)
    if validation_error is not None:
        return validation_error
    for field in EDITABLE_FIELDS:
        setattr(sheet, field, values.get(field, getattr(sheet, field)))
    sheet.demography_revision += 1
    sheet.save(update_fields=[*EDITABLE_FIELDS, "demography_revision"])
    if "preflight" in values:
        preflight.save(sheet, values["preflight"])
    if "cruise" in values:
        cruise.save(sheet, values["cruise"])
    if "approach" in values:
        approach.save(sheet, values["approach"])
    if "final_crew_mark" in values:
        final_crew.save(sheet, values["final_crew_mark"])
    if "observations" in values:
        observations.save(sheet, values["observations"])
    if "stage_assessments" in values:
        stage_assessments.save(sheet, values["stage_assessments"])
    # Lock pilots in a stable order when concurrent audits share a crew.
    pilots = {
        pilot.pk: pilot
        for pilot in Pilot.objects.select_for_update()
        .filter(pk__in=[sheet.captain_id, sheet.first_officer_id])
        .order_by("pk")
    }
    for pilot_id, prefix in (
        (sheet.captain_id, "captain"),
        (sheet.first_officer_id, "first_officer"),
    ):
        pilot = pilots[pilot_id]
        changed_fields = []
        for field in ("experience", "type_experience"):
            value = getattr(sheet, f"{prefix}_{field}")
            if value is not None:
                setattr(pilot, field, value)
                changed_fields.append(field)
        if changed_fields:
            pilot.save(update_fields=changed_fields)
    assignment.audit_sheet = sheet
    return JsonResponse(response_payload(assignment))


@never_cache
@require_http_methods(["GET", "PUT"])
@csrf_protect
@portal_required
def save_demography(request, pk):
    if request.method == "GET":
        with transaction.atomic():
            assignment = locked_assignment(request.user, pk)
            if not can_view(assignment, request.user):
                return JsonResponse({"detail": "Нет доступа к этой проверке."}, status=403)
            if not assignment.audit_sheet_id:
                return JsonResponse({"detail": "Лист еще не открыт аудитором."}, status=404)
            assignment.audit_sheet = AuditSheet.objects.select_for_update().get(
                pk=assignment.audit_sheet_id
            )
            return JsonResponse(response_payload(assignment))
    from .views import read_json
    values, error = deserialize_values(read_json(request))
    if error is not None:
        return error
    with transaction.atomic():
        assignment = locked_assignment(request.user, pk)
        if not can_start(assignment, request.user) or not assignment.audit_sheet_id or not assignment.opened_at:
            return JsonResponse({"detail": "Нет доступа к сохранению этого черновика."}, status=403)
        return apply_locked_values(assignment, values)
