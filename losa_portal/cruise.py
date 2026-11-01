from rest_framework import serializers
from losa.models import AssessmentStage, AuditAssessment

STAGE_CODE = "cruise"
STAGE_NAME = "Крейсерский режим"


class CruiseSerializer(serializers.Serializer):
    facts = serializers.CharField(allow_blank=True, trim_whitespace=False)


def stage():
    value = AssessmentStage.objects.filter(code=STAGE_CODE).first()
    if value is None:
        raise serializers.ValidationError(
            "Не подготовлен крейсерский этап. Выполните python manage.py setup_losa_cruise."
        )
    return value


def seed():
    value, _ = AssessmentStage.objects.get_or_create(
        code=STAGE_CODE, defaults={"name": STAGE_NAME, "sort_order": 2}
    )
    return value


def read(sheet):
    row = AuditAssessment.objects.filter(
        audit_sheet=sheet, stage__code=STAGE_CODE
    ).first()
    return {"facts": row.facts if row else ""}


def save(sheet, data):
    AuditAssessment.objects.update_or_create(
        audit_sheet=sheet, stage=stage(), defaults={"facts": data["facts"]}
    )
