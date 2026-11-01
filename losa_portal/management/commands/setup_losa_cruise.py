from django.core.management.base import BaseCommand
from losa_portal.cruise import seed


class Command(BaseCommand):
    help = "Подготовить крейсерский этап оценки LOSA без изменения существующих записей."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f"Готово: {seed()}."))
