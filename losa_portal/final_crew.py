"""Final crew observations, one editable record per audit sheet."""
from rest_framework import serializers
from losa.models import FinalMarkCrew

SCORE_FIELDS = (
    "free_communication", "capt_as_leader", "general_mark_capt",
    "general_mark_copilot", "total_general_mark",
)
FIELDS = ("preflight_brief_with_fa", *SCORE_FIELDS, "general_notes")


class FinalCrewSerializer(serializers.Serializer):
    preflight_brief_with_fa = serializers.ChoiceField(
        choices=FinalMarkCrew.PREFLIGHT_BRIEF_CHOICES, allow_null=True
    )
    free_communication = serializers.ChoiceField(choices=FinalMarkCrew.MARK_CHOICES, allow_null=True)
    capt_as_leader = serializers.ChoiceField(choices=FinalMarkCrew.MARK_CHOICES, allow_null=True)
    general_mark_capt = serializers.ChoiceField(choices=FinalMarkCrew.MARK_CHOICES, allow_null=True)
    general_mark_copilot = serializers.ChoiceField(choices=FinalMarkCrew.MARK_CHOICES, allow_null=True)
    total_general_mark = serializers.ChoiceField(choices=FinalMarkCrew.MARK_CHOICES, allow_null=True)
    general_notes = serializers.CharField(allow_blank=True, trim_whitespace=False)

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(FIELDS):
            raise serializers.ValidationError("Переданы неизвестные поля итоговой оценки.")
        return super().to_internal_value(data)


def catalog():
    return {
        "brief_choices": list(FinalMarkCrew.PREFLIGHT_BRIEF_CHOICES),
        "brief_label": str(FinalMarkCrew._meta.get_field("preflight_brief_with_fa").verbose_name),
        "score_choices": list(FinalMarkCrew.MARK_CHOICES),
        "scores": [
            {"field": field, "label": str(FinalMarkCrew._meta.get_field(field).verbose_name)}
            for field in SCORE_FIELDS
        ],
    }


def read(sheet):
    row = FinalMarkCrew.objects.filter(audit_sheet=sheet).first()
    if row:
        return {field: getattr(row, field) for field in FIELDS}
    return {field: "" if field == "general_notes" else None for field in FIELDS}


def save(sheet, data):
    # Do not create a record merely because an untouched empty form was submitted.
    if any(value is not None and value != "" for value in data.values()) or FinalMarkCrew.objects.filter(audit_sheet=sheet).exists():
        FinalMarkCrew.objects.update_or_create(audit_sheet=sheet, defaults=data)
