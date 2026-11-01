from django.core.management.base import BaseCommand
from losa_portal.models import AuditAssignment


class Command(BaseCommand):
    help = "Присвоить номера ранее созданным назначениям"

    def handle(self, *args, **options):
        total = 0
        for assignment in AuditAssignment.objects.filter(number__isnull=True).order_by(
            "created_at", "pk"
        ):
            assignment.save(update_fields=["number"])
            total += 1
        self.stdout.write(self.style.SUCCESS(f"Пронумеровано назначений: {total}"))
