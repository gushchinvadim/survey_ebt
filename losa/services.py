# losa/services.py
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    AssessmentStage,
    AssessmentCriterion,
    AuditSheet,
    AuditAssessment,
    AuditRating,
)


@transaction.atomic
def initialize_assessments(audit_sheet):
    sheet = AuditSheet.objects.select_for_update().get(pk=audit_sheet.pk)

    if not sheet.assessment_template_id:
        raise ValidationError("Сначала выбери шаблон оценки.")

    stage_codes = [
        "preflight_taxi",
        "cruise",
        "descent_landing",
    ]
    stages = list(
        AssessmentStage.objects.filter(code__in=stage_codes)
    )
    criteria = list(
        AssessmentCriterion.objects.filter(
            section__template_id=sheet.assessment_template_id,
        )
    )

    if len(stages) != 3:
        raise ValidationError(
            "Не найдены три этапа оценки. Выполни seed_assessment."
        )

    if not criteria:
        raise ValidationError("В выбранном шаблоне нет критериев.")

    for stage in stages:
        assessment, _ = AuditAssessment.objects.get_or_create(
            audit_sheet=sheet,
            stage=stage,
        )

        for criterion in criteria:
            AuditRating.objects.get_or_create(
                assessment=assessment,
                criterion=criterion,
            )