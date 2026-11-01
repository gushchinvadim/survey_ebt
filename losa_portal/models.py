import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class PortalProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="losa_profile",
        verbose_name="Пользователь",
    )
    auditor = models.OneToOneField(
        "losa.Auditor",
        on_delete=models.PROTECT,
        related_name="portal_profile",
        verbose_name="Аудитор",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Профиль пользователя LOSA"
        verbose_name_plural = "Профили пользователей LOSA"

    def __str__(self):
        return self.user.get_username()


class Flight(models.Model):
    number = models.CharField("Номер рейса", max_length=30)
    departure = models.ForeignKey(
        "losa.Airport",
        on_delete=models.PROTECT,
        related_name="portal_departure_flights",
        verbose_name="Аэропорт вылета",
    )
    arrival = models.ForeignKey(
        "losa.Airport",
        on_delete=models.PROTECT,
        related_name="portal_arrival_flights",
        verbose_name="Аэропорт прилёта",
    )
    time = models.TimeField("Время вылета по часовому поясу программы")
    aircraft = models.ForeignKey(
        "losa.Aircraft",
        on_delete=models.PROTECT,
        related_name="portal_flights",
        verbose_name="Тип ВС",
    )
    is_active = models.BooleanField("Доступен для планирования", default=True)

    class Meta:
        verbose_name = "Рейс программы LOSA"
        verbose_name_plural = "Рейсы программы LOSA"
        ordering = ["time", "pk"]

    def __str__(self):
        return f"{self.number}: {self.departure.airport_code} → {self.arrival.airport_code}"


class AuditNumberCounter(models.Model):
    key = models.CharField(max_length=30, primary_key=True)
    last_number = models.PositiveBigIntegerField(default=0)


class AuditAssignment(models.Model):
    STATUS_CHOICES = [("scheduled", "Запланирована"), ("completed", "Завершена")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.PositiveBigIntegerField(
        "Порядковый номер проверки", unique=True, null=True, blank=True, editable=False
    )
    audit_sheet = models.OneToOneField(
        "losa.AuditSheet",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="portal_assignment",
        verbose_name="Лист аудита",
    )
    opened_at = models.DateTimeField(
        "Начало заполнения", null=True, blank=True, editable=False
    )
    date = models.DateField("Дата проверки")
    flight = models.ForeignKey(
        Flight,
        on_delete=models.PROTECT,
        related_name="assignments",
        verbose_name="Рейс",
    )
    captain = models.ForeignKey(
        "losa.Pilot",
        on_delete=models.PROTECT,
        related_name="portal_captain_assignments",
        verbose_name="КВС",
    )
    first_officer = models.ForeignKey(
        "losa.Pilot",
        on_delete=models.PROTECT,
        related_name="portal_officer_assignments",
        verbose_name="Второй пилот",
    )
    auditor = models.ForeignKey(
        "losa.Auditor",
        on_delete=models.PROTECT,
        related_name="portal_assignments",
        verbose_name="Аудитор",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=STATUS_CHOICES,
        default="scheduled",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_losa_assignments",
        verbose_name="Кто назначил",
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Назначенная проверка"
        verbose_name_plural = "Назначенные проверки"
        ordering = ["date", "flight__time", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["date", "flight"], name="unique_portal_flight_date"
            ),
            models.CheckConstraint(
                condition=~models.Q(captain=models.F("first_officer")),
                name="portal_different_pilots",
            ),
        ]

    def clean(self):
        super().clean()
        if self.captain_id and self.captain_id == self.first_officer_id:
            raise ValidationError(
                {"first_officer": "КВС и второй пилот должны быть разными."}
            )

    def __str__(self):
        return f"{self.date} — {self.flight}"

    @property
    def audit_number(self):
        return f"LOSA-{self.number:06d}" if self.number is not None else "Не присвоен"

    def save(self, *args, **kwargs):
        if self.number is not None:
            return super().save(*args, **kwargs)
        from django.db import transaction
        from django.db.models import Max
        from django.db import router
        from losa.models import AuditSheet

        database = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=database):
            AuditNumberCounter.objects.using(database).get_or_create(key="audit")
            counter = (
                AuditNumberCounter.objects.using(database)
                .select_for_update()
                .get(key="audit")
            )
            existing = (
                type(self).objects.using(database).aggregate(last=Max("number"))["last"]
                or 0
            )
            number = max(counter.last_number, existing) + 1
            while (
                AuditSheet.objects.using(database)
                .filter(audit_number=f"LOSA-{number:06d}")
                .exists()
            ):
                number += 1
            counter.last_number = number
            counter.save(using=database, update_fields=["last_number"])
            self.number = number
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"number"}
            return super().save(*args, **kwargs)
