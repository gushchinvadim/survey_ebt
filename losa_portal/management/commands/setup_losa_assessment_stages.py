from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from losa.models import AssessmentStage, AssessmentTemplate, AuditCriterionRating
from losa_portal.stage_assessments import STAGES


class Command(BaseCommand):
    help = "Подготовить четыре этапа и привязать отдельные шаблоны без копирования критериев."

    @transaction.atomic
    def handle(self, *args, **options):
        for order, (code, name) in enumerate(STAGES, 1):
            stage, _ = AssessmentStage.objects.get_or_create(
                code=code, defaults={"name": name, "sort_order": order}
            )
            if not stage.template_id:
                template = None
                if code == "preflight":
                    version = getattr(settings, "LOSA_ASSESSMENT_TEMPLATE_VERSION", "portal-v1")
                    template = AssessmentTemplate.objects.filter(version=version).first()
                    if template is None:
                        ids = list(AuditCriterionRating.objects.filter(stage=stage).values_list(
                            "criterion__section__template_id", flat=True
                        ).distinct())
                        if len(ids) == 1:
                            template = AssessmentTemplate.objects.get(pk=ids[0])
                if template is None:
                    version = "portal-v1" if code == "preflight" else f"{code}-v1"
                    template, _ = AssessmentTemplate.objects.get_or_create(
                        version=version, defaults={"name": name[:100]}
                    )
                stage.template = template
            stage.sort_order = order
            stage.save(update_fields=["template", "sort_order"])
            self.stdout.write(f"{stage.name}: {stage.template}")
        self.stdout.write(self.style.SUCCESS(
            "Готово. Заполните разделы и критерии нужных шаблонов в админке. Существующие оценки сохранены."
        ))
