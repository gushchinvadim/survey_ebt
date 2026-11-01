from django.core.management.base import BaseCommand
from django.db import transaction
from losa_portal.preflight import seed


class Command(BaseCommand):
    help = "Подготовить 11 критериев предполетной оценки для портала, сохранив существующие данные."

    @transaction.atomic
    def handle(self, *args, **options):
        stage, template = seed()
        self.stdout.write(self.style.SUCCESS(f"Готово: {stage}; шаблон {template}."))
