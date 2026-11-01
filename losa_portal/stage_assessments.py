"""Stage-specific sections/criteria from the admin, with existing ratings preserved."""
from rest_framework import serializers
from losa.models import (
    AssessmentStage, AssessmentSection, AssessmentCriterion,
    AuditAssessment, AuditCriterionRating,
)

STAGES = (
    ("preflight", "Предполетная подготовка / выруливание на взлетную позицию"),
    ("takeoff_climb", "Взлет и набор высоты"),
    ("cruise", "Крейсерский режим"),
    ("descent_landing", "Снижение / заход на посадку / посадка и руление"),
)
STAGE_CODES = {code for code, _ in STAGES}


class StageValueSerializer(serializers.Serializer):
    facts = serializers.CharField(allow_blank=True, trim_whitespace=False)
    scores = serializers.DictField(
        child=serializers.ChoiceField(choices=[1, 2, 3, 4], allow_null=True)
    )

    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - {"facts", "scores"}:
            raise serializers.ValidationError("Переданы неизвестные поля оценки этапа.")
        return super().to_internal_value(data)


class StageAssessmentsSerializer(serializers.DictField):
    def __init__(self, **kwargs):
        super().__init__(child=StageValueSerializer(), **kwargs)

    def to_internal_value(self, data):
        result = super().to_internal_value(data)
        if set(result) - STAGE_CODES:
            raise serializers.ValidationError("Неизвестный этап оценки.")
        return result


def bundle(sheet):
    stages = {
        row.code: row for row in AssessmentStage.objects.filter(code__in=STAGE_CODES)
        .select_related("template")
    }
    catalog, form = {}, {}
    for code, default_name in STAGES:
        stage = stages.get(code)
        sections = []
        current_ids = set()
        if stage and stage.template_id:
            for section in AssessmentSection.objects.filter(
                template_id=stage.template_id
            ).prefetch_related("criteria").order_by("number", "pk"):
                items = [
                    {"id": row.pk, "code": row.code, "name": row.name}
                    for row in section.criteria.order_by("sort_order", "pk")
                ]
                current_ids.update(row["id"] for row in items)
                sections.append({"id": str(section.pk), "number": section.number,
                                 "name": section.name, "criteria": items, "historical": False})
        ratings = list(AuditCriterionRating.objects.filter(
            audit_sheet=sheet, stage=stage
        ).select_related("criterion__section__template")) if stage else []
        # Keep visible/editable ratings from previously used templates, without moving them.
        historical = {}
        for rating in ratings:
            criterion = rating.criterion
            if criterion.pk in current_ids:
                continue
            section = criterion.section
            group = historical.setdefault(section.pk, {
                "id": f"previous-{section.pk}", "number": section.number,
                "name": section.name,
                "template_version": section.template.version,
                "criteria": [], "historical": True,
            })
            group["criteria"].append({"id": criterion.pk, "code": criterion.code, "name": criterion.name})
        sections.extend(sorted(historical.values(), key=lambda row: (row["number"], row["id"])))
        facts_row = AuditAssessment.objects.filter(audit_sheet=sheet, stage=stage).first() if stage else None
        scores = {str(row["id"]): None for section in sections for row in section["criteria"]}
        scores.update({str(row.criterion_id): row.score for row in ratings})
        form[code] = {"facts": facts_row.facts if facts_row else "", "scores": scores}
        catalog[code] = {
            "id": stage.pk if stage else None, "name": stage.name if stage else default_name,
            "configured": bool(stage and stage.template_id),
            "template_id": stage.template_id if stage else None,
            "template_version": stage.template.version if stage and stage.template_id else None,
            "sections": sections,
        }
    return {"catalog": catalog, "form": form}


def validate_for_sheet(sheet, values):
    available = bundle(sheet)
    for code, data in values.items():
        definition = available["catalog"][code]
        if not definition["id"] and (data["facts"] or data["scores"]):
            raise serializers.ValidationError("Подготовьте этапы: python manage.py setup_losa_assessment_stages.")
        invalid = set(data["scores"]) - set(available["form"][code]["scores"])
        if invalid:
            raise serializers.ValidationError({
                code: "Состав критериев изменился или выбран критерий другого этапа. Обновите форму; локальный черновик сохранён."
            })


def same_as_stored(sheet, values):
    stored = bundle(sheet)["form"]
    return all(
        data["facts"] == stored[code]["facts"]
        and all(key in stored[code]["scores"] and stored[code]["scores"][key] == score
                for key, score in data["scores"].items())
        for code, data in values.items()
    )


def save(sheet, values):
    stages = {row.code: row for row in AssessmentStage.objects.filter(code__in=values)}
    for code, data in values.items():
        stage = stages.get(code)
        if not stage:
            continue
        if data["facts"] or AuditAssessment.objects.filter(audit_sheet=sheet, stage=stage).exists():
            AuditAssessment.objects.update_or_create(
                audit_sheet=sheet, stage=stage, defaults={"facts": data["facts"]}
            )
        for criterion_id, score in data["scores"].items():
            queryset = AuditCriterionRating.objects.filter(
                audit_sheet=sheet, stage=stage, criterion_id=int(criterion_id)
            )
            if score is not None or queryset.exists():
                # Do not overwrite comments from the admin or omit historical records.
                AuditCriterionRating.objects.update_or_create(
                    audit_sheet=sheet, stage=stage, criterion_id=int(criterion_id),
                    defaults={"score": score},
                )
