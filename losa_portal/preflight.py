"""Preflight crew assessment, stored in the existing LOSA assessment tables."""
from django.conf import settings
from rest_framework import serializers
from losa.models import (
    AssessmentStage, AssessmentTemplate, AssessmentSection, AssessmentCriterion,
    AuditAssessment, AuditCriterionRating,
)

STAGE_CODE = "preflight"
STAGE_NAME = "Предполетная подготовка / выруливание на взлетную позицию"
SECTIONS = [
    (1, "Качественная характеристика работы экипажа с планом полета", [
        ("1-1", "Предполетный инструктаж КВС по SOP"),
        ("1-2", "Рассмотрение планов полета"),
        ("1-3", "Загрузка членов экипажа"),
        ("1-4", "Контроль непредвиденных обстоятельств"),
    ]),
    (2, "Качественная характеристика выполнения экипажем требуемых действий", [
        ("2-1", "Контроль показаний приборов / перекрестный контроль"),
        ("2-2", "Загрузка членов экипажа"),
        ("2-3", "Внимательность"),
        ("2-4", "Управление работой автоматических систем"),
    ]),
    (3, "Качественная характеристика действий экипажа при рассмотрении и уточнении планов полета", [
        ("3-1", "Критическая оценка планов полета"),
        ("3-2", "Обращения за пояснениями"),
        ("3-3", "Убежденность"),
    ]),
]
CODES = [code for _, _, criteria in SECTIONS for code, _ in criteria]


def template_version():
    return getattr(settings, "LOSA_ASSESSMENT_TEMPLATE_VERSION", "portal-v1")


def catalog():
    return {
        "stage": STAGE_NAME,
        "sections": [
            {"number": number, "name": name,
             "criteria": [{"code": code, "name": label} for code, label in criteria]}
            for number, name, criteria in SECTIONS
        ],
    }


def definitions():
    stage = AssessmentStage.objects.filter(code=STAGE_CODE).first()
    criteria = {
        item.code: item for item in AssessmentCriterion.objects.filter(
            section__template__version=template_version(), code__in=CODES
        ).select_related("section")
    }
    if stage is None or set(criteria) != set(CODES):
        raise serializers.ValidationError(
            "Не подготовлены критерии. Выполните python manage.py setup_losa_preflight."
        )
    return stage, criteria


def seed():
    stage, _ = AssessmentStage.objects.get_or_create(
        code=STAGE_CODE, defaults={"name": STAGE_NAME, "sort_order": 1}
    )
    template, _ = AssessmentTemplate.objects.get_or_create(
        version=template_version(), defaults={"name": "Оценка экипажа LOSA"}
    )
    for number, name, items in SECTIONS:
        section, _ = AssessmentSection.objects.get_or_create(
            template=template, number=number, defaults={"name": name}
        )
        for index, (code, label) in enumerate(items, 1):
            AssessmentCriterion.objects.get_or_create(
                section=section, code=code, defaults={"name": label, "sort_order": index}
            )
    return stage, template


class PreflightSerializer(serializers.Serializer):
    facts = serializers.CharField(allow_blank=True, trim_whitespace=False)
    scores = serializers.DictField(
        child=serializers.ChoiceField(choices=[1, 2, 3, 4], allow_null=True)
    )

    def validate_scores(self, value):
        if set(value) != set(CODES):
            raise serializers.ValidationError("Передайте все 11 критериев, незаполненные — null.")
        return value


def read(sheet):
    stage = AssessmentStage.objects.filter(code=STAGE_CODE).first()
    facts = ""
    scores = dict.fromkeys(CODES)
    if stage:
        assessment = AuditAssessment.objects.filter(audit_sheet=sheet, stage=stage).first()
        if assessment:
            facts = assessment.facts
        for rating in AuditCriterionRating.objects.filter(
            audit_sheet=sheet, stage=stage,
            criterion__section__template__version=template_version(),
            criterion__code__in=CODES,
        ).select_related("criterion"):
            scores[rating.criterion.code] = rating.score
    return {"facts": facts, "scores": scores}


def save(sheet, data):
    stage, criteria = definitions()
    AuditAssessment.objects.update_or_create(
        audit_sheet=sheet, stage=stage, defaults={"facts": data["facts"]}
    )
    for code in CODES:
        # Comments from admin are deliberately preserved.
        AuditCriterionRating.objects.update_or_create(
            audit_sheet=sheet, stage=stage, criterion=criteria[code],
            defaults={"score": data["scores"][code]},
        )
