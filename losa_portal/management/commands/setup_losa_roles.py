from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from losa_portal.access import COORDINATOR_GROUP, AUDITOR_GROUP


class Command(BaseCommand):
    help = "Создать группы ролей LOSA без назначения пользователей"

    def handle(self, *args, **options):
        for name in (COORDINATOR_GROUP, AUDITOR_GROUP):
            Group.objects.get_or_create(name=name)
        self.stdout.write(
            self.style.SUCCESS(
                "Группы LOSA созданы. Назначьте их пользователям в админке."
            )
        )
