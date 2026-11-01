# losa/management/commands/seed_assessment.py
from django.core.management.base import BaseCommand
from django.db import transaction

from losa.models import (
    AssessmentStage,
    AssessmentTemplate,
    AssessmentSection,
    AssessmentCriterion,
)


STAGES = [
    (
        "preflight_taxi",
        "Предполётная подготовка / выруливание на взлётную позицию",
    ),
    ("cruise", "Крейсерский режим"),
    (
        "descent_landing",
        "Снижение / заход на посадку / посадка и руление",
    ),
]

SECTIONS = [
    (
        "Качественная характеристика работы экипажа с планом полёта",
        [
            "Инструктаж КВС по SOP",
            "Рассмотрение планов полёта",
            "Загрузка членов экипажа",
            "Контроль непредвиденных обстоятельств",
        ],
    ),
    (
        "Качественная характеристика выполнения экипажем требуемых действий",
        [
            "Контроль показаний приборов / перекрёстный контроль",
            "Загрузка членов экипажа",
            "Внимательность",
            "Управление работой автоматических систем",
        ],
    ),
    (
        "Качественная характеристика действий экипажа "
        "при рассмотрении и уточнении планов полёта",
        [
            "Критическая оценка планов полёта",
            "Обращения за пояснениями",
            "Убеждённость",
        ],
    ),
]


class Command(BaseCommand):
    help = "Создать исходный шаблон оценки экипажа"

    @transaction.atomic
    def handle(self, *args, **options):
        for order, (code, name) in enumerate(STAGES, start=1):
            AssessmentStage.objects.get_or_create(
                code=code,
                defaults={"name": name, "sort_order": order},
            )

        template, _ = AssessmentTemplate.objects.get_or_create(
            version="1",
            defaults={"name": "Оценка работы экипажа"},
        )

        for number, (name, criteria) in enumerate(SECTIONS, start=1):
            section, _ = AssessmentSection.objects.get_or_create(
                template=template,
                number=number,
                defaults={"name": name},
            )

            for order, criterion_name in enumerate(criteria, start=1):
                AssessmentCriterion.objects.get_or_create(
                    section=section,
                    code=f"{number}-{order}",
                    defaults={
                        "name": criterion_name,
                        "sort_order": order,
                    },
                )

        self.stdout.write(self.style.SUCCESS(
            "Шаблон версии 1 и этапы оценки подготовлены."
        ))