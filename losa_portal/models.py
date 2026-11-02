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


class ObservationTopic(models.Model):
    name = models.CharField("Тема или подтема", max_length=160, unique=True)
    parent = models.ForeignKey("self", verbose_name="Родительская тема", null=True, blank=True,
                               on_delete=models.PROTECT, related_name="subtopics")

    class Meta:
        verbose_name = "Тема наблюдений"
        verbose_name_plural = "Темы наблюдений"
        ordering = ["name"]

    def clean(self):
        seen = {self.pk} if self.pk else set()
        parent = self.parent
        while parent:
            if parent.pk in seen:
                raise ValidationError({"parent": "Темы не должны образовывать цикл."})
            seen.add(parent.pk)
            parent = parent.parent

    def __str__(self):
        return self.name


class TextObservation(models.Model):
    NATURES = [("difficulty", "Затруднение"), ("practice", "Удачная практика"),
               ("neutral", "Нейтральное наблюдение")]
    EVIDENCE = [("fact", "Описание фактов или действий"), ("opinion", "Впечатление аудитора"),
                ("mixed", "Факты и оценочное суждение")]
    STATUSES = [("included", "Включено в анализ"), ("excluded", "Исключено из анализа")]
    audit_sheet = models.ForeignKey("losa.AuditSheet", on_delete=models.PROTECT,
                                    related_name="text_observations", verbose_name="Лист аудита")
    assessment = models.ForeignKey("losa.AuditAssessment", on_delete=models.PROTECT,
                                   null=True, blank=True, verbose_name="Изложение фактов по этапу")
    final_mark = models.ForeignKey("losa.FinalMarkCrew", on_delete=models.PROTECT,
                                   null=True, blank=True, verbose_name="Общее впечатление")
    round_table_review = models.ForeignKey("SourceReview", on_delete=models.PROTECT,
        null=True, blank=True, related_name="observations", verbose_name="Решение круглого стола")
    source_snapshot = models.TextField("Текст источника при включении")
    quote = models.TextField("Точная цитата")
    topics = models.ManyToManyField(ObservationTopic, verbose_name="Темы / подтемы", related_name="observations")
    nature = models.CharField("Характер", max_length=20, choices=NATURES)
    evidence = models.CharField("Основание", max_length=20, choices=EVIDENCE)
    note = models.TextField("Пояснение координатора", blank=True)
    status = models.CharField("Участие в анализе", max_length=20, choices=STATUSES, default="included")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="created_text_observations", verbose_name="Кто включил")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="updated_text_observations", verbose_name="Кто изменил")
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Изменено", auto_now=True)

    class Meta:
        verbose_name = "Аналитическое наблюдение"
        verbose_name_plural = "Аналитические наблюдения"
        ordering = ["-created_at", "-pk"]
        constraints = [models.CheckConstraint(
            condition=(models.Q(assessment__isnull=False, final_mark__isnull=True)
                       | models.Q(assessment__isnull=True, final_mark__isnull=False)),
            name="text_observation_exactly_one_source")]

    @property
    def current_source(self):
        if self.round_table_review_id:
            return self.round_table_review.agreed_text
        return self.assessment.facts if self.assessment_id else self.final_mark.general_notes

    @property
    def source_changed(self):
        return (self.current_source != self.source_snapshot or
                bool(self.round_table_review_id and self.round_table_review.original_changed))

    @property
    def source_label(self):
        return str(self.assessment.stage) if self.assessment_id else "Общее впечатление"

    def clean(self):
        if bool(self.assessment_id) == bool(self.final_mark_id):
            raise ValidationError("Укажите один источник текста.")
        source = self.assessment if self.assessment_id else self.final_mark
        if source.audit_sheet_id != self.audit_sheet_id:
            raise ValidationError("Источник должен принадлежать указанному листу.")
        if self.round_table_review_id:
            review = self.round_table_review
            if review.assessment_id != self.assessment_id or review.final_mark_id != self.final_mark_id:
                raise ValidationError("Карточка должна соответствовать источнику решения круглого стола.")
        if not self.quote.strip() or self.quote not in self.source_snapshot:
            raise ValidationError({"quote": "Цитата должна быть точным непустым фрагментом источника."})

    def __str__(self):
        return f"{self.audit_sheet.audit_number} / {self.source_label}: {self.quote[:70]}"


class RoundTableCycle(models.Model):
    name = models.CharField("Название цикла", max_length=200)
    assignments = models.ManyToManyField(AuditAssignment, related_name="review_cycles", verbose_name="Проверки")
    closed = models.BooleanField("Обсуждение завершено", default=False)
    revision = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="round_table_cycles")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        verbose_name = "Цикл круглого стола"
        verbose_name_plural = "Циклы круглого стола"


class SourceReview(models.Model):
    DECISIONS = [('confirmed', 'Подтверждено без изменений'), ('revised', 'Уточнено по итогам обсуждения'),
                 ('pending', 'Требует уточнения')]
    cycle = models.ForeignKey(RoundTableCycle, on_delete=models.PROTECT, related_name="reviews")
    assessment = models.ForeignKey('losa.AuditAssessment', on_delete=models.PROTECT, null=True, blank=True)
    final_mark = models.ForeignKey('losa.FinalMarkCrew', on_delete=models.PROTECT, null=True, blank=True)
    source_snapshot = models.TextField()
    agreed_text = models.TextField(blank=True)
    history = models.JSONField(default=list, blank=True)
    decision = models.CharField(max_length=20, choices=DECISIONS)
    note = models.TextField(blank=True)
    revision = models.PositiveIntegerField(default=1)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def original_text(self):
        return self.assessment.facts if self.assessment_id else self.final_mark.general_notes

    @property
    def original_changed(self):
        return self.original_text != self.source_snapshot

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['cycle', 'assessment'], name='unique_cycle_assessment_review'),
            models.UniqueConstraint(fields=['cycle', 'final_mark'], name='unique_cycle_final_review'),
            models.CheckConstraint(condition=(models.Q(assessment__isnull=False, final_mark__isnull=True)
                | models.Q(assessment__isnull=True, final_mark__isnull=False)), name='source_review_exactly_one_source')]
