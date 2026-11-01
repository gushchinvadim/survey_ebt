from random import choices

from django.utils import timezone
from django.db import models
from django.core.exceptions import ValidationError


class Location(models.Model):
    location_name = models.CharField("Название", max_length=100)
    location_code = models.CharField("Код", max_length=100)
    address = models.CharField("Адрес", max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = "Местоположение"
        verbose_name_plural = "Местоположения"
        ordering = ["location_name", "pk"]

    def __str__(self):
        return f"{self.location_name} ({self.location_code})"


class Company(models.Model):
    company_name = models.CharField("Название компании", max_length=100)
    company_code = models.CharField("Код компании", max_length=100)

    class Meta:
        verbose_name = "Компания"
        verbose_name_plural = "Компании"
        ordering = ["company_name", "pk"]

    def __str__(self):
        return f"{self.company_name} ({self.company_code})"


class Pilot(models.Model):
    POSITION_CHOICES = [
        ("CAPT", "Командир ВС"),
        ("FO", "Второй пилот"),
        ("Observer", "Дополнительный пилот"),
        ("FE", "Бортинженер"),
    ]
    pilot_id = models.IntegerField("Номер сотрудника в компании")
    company = models.ForeignKey(
        Company,
        verbose_name="Компания",
        on_delete=models.PROTECT,
        related_name="pilots",
    )
    location = models.ForeignKey(
        Location,
        verbose_name="Местоположение",
        on_delete=models.PROTECT,
        related_name="pilots",
    )
    position = models.CharField("Должность", max_length=20, choices=POSITION_CHOICES)
    experience = models.PositiveIntegerField(
        "Общий стаж лётной работы", help_text="Количество полных лет", null=True, blank=True,
    )
    type_experience = models.PositiveIntegerField(
        "Стаж на данном типе", help_text="Количество полных лет", null=True, blank=True,
    )

    class Meta:
        verbose_name = "Пилот"
        verbose_name_plural = "Пилоты"
        ordering = ["company_id", "pilot_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "pilot_id"], name="unique_pilot_number_per_company"
            )
        ]

    def __str__(self):
        return f"{self.company.company_code} / {self.pilot_id}"

    fmc_experience = models.PositiveIntegerField(
        "Стаж полётов на ВС с автоматическими системами",
        help_text="Количество полных лет",
        null=True,
        blank=True,
    )


class Auditor(models.Model):
    auditor_code = models.IntegerField("Код аудитора")
    name = models.CharField("ФИО", max_length=100)

    class Meta:
        verbose_name = "Аудитор"
        verbose_name_plural = "Аудиторы"
        ordering = ["name", "pk"]

    def __str__(self):
        return f"{self.name} ({self.auditor_code})"


class Aircraft(models.Model):
    aircraft_type = models.CharField("Тип ВС", max_length=100)

    class Meta:
        verbose_name = "Тип воздушного судна"
        verbose_name_plural = "Типы воздушных судов"
        ordering = ["aircraft_type", "pk"]

    def __str__(self):
        return self.aircraft_type


class Airport(models.Model):
    airport_code = models.CharField("Код аэропорта", max_length=100)
    airport_name = models.CharField("Название аэропорта", max_length=100)

    class Meta:
        verbose_name = "Аэропорт"
        verbose_name_plural = "Аэропорты"
        ordering = ["airport_code", "pk"]

    def __str__(self):
        return f"{self.airport_code} — {self.airport_name}"


class MistakeType(models.Model):
    code = models.CharField("Код типа", max_length=20, unique=True)
    name = models.CharField("Название типа", max_length=100)
    describe = models.TextField("Пояснение к типу", blank=True)

    class Meta:
        verbose_name = "Тип ошибки"
        verbose_name_plural = "Типы ошибок"
        ordering = ["code"]

    def __str__(self):
        return self.name


class MistakeSection(models.Model):
    type = models.ForeignKey(
        MistakeType,
        verbose_name="Тип ошибки",
        on_delete=models.PROTECT,
        related_name="sections",
    )
    name = models.CharField("Название раздела", max_length=200)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Раздел ошибок"
        verbose_name_plural = "Разделы ошибок"
        ordering = ["type__code", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["type", "name"], name="unique_mistake_section_per_type"
            )
        ]

    def __str__(self):
        return f"{self.type} — {self.name}"


class Mistake(models.Model):
    code = models.CharField("Код ошибки", max_length=100, unique=True)
    name = models.CharField("Название ошибки", max_length=300)
    type = models.ForeignKey(
        MistakeType,
        verbose_name="Тип ошибки",
        on_delete=models.PROTECT,
        related_name="mistakes",
    )
    section = models.ForeignKey(
        MistakeSection,
        verbose_name="Раздел",
        on_delete=models.PROTECT,
        related_name="mistakes",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Ошибка"
        verbose_name_plural = "Ошибки"
        ordering = ["type__code", "code"]

    def clean(self):
        super().clean()
        if self.section_id and self.type_id:
            if self.section.type_id != self.type_id:
                raise ValidationError(
                    {"section": "Этот раздел относится к другому типу ошибки."}
                )

    def __str__(self):
        return f"{self.code} — {self.name}"


class Threat(models.Model):
    THREAT_TYPE_CHOICES = [
        ("departure_arrival", "Вылет/прибытие"),
        ("aircraft_condition", "Состояние ВС"),
        ("flight_operations", "Выполнение полётного задания"),
        ("onboard", "Борт ВС"),
        ("atc", "Служба ОрВД"),
        ("flight_support", "Служба обеспечения полёта"),
        ("other_factors", "Другие факторы угрозы"),
    ]
    code = models.CharField("Код угрозы", max_length=100)
    type = models.CharField(
        "Категория угрозы", max_length=30, choices=THREAT_TYPE_CHOICES
    )
    describe = models.CharField("Описание", max_length=1000)

    class Meta:
        verbose_name = "Фактор угрозы"
        verbose_name_plural = "Факторы угроз"
        ordering = ["code", "pk"]

    def __str__(self):
        return f"{self.code} — {self.describe[:80]}"


class AuditSheet(models.Model):
    WORKING_TOGETHER_CHOICE = [
        ("1", "Впервые"),
        ("2", "Второй лег"),
        ("3", "Ранее работали вместе"),
    ]
    PF_CHOICE = [("1", "Командир ВС"), ("2", "Второй пилот"), ("3", "Пилот-инструктор")]
    LEG_NUMBER_CHOICE = [
        ("1 из 1", "1 из 1"),
        ("1 из 2", "1 из 2"),
        ("2 из 2", "2 из 2"),
        ("1 из 3", "1 из 3"),
        ("2 из 3", "2 из 3"),
        ("3 из 3", "3 из 3"),
    ]
    audit_number = models.CharField("Номер проверки", max_length=100)
    date = models.DateField("Дата проверки", default=timezone.localdate)
    auditor = models.ForeignKey(
        Auditor,
        verbose_name="Аудитор",
        on_delete=models.PROTECT,
        related_name="audit_sheets",
    )
    aircraft = models.ForeignKey(
        Aircraft,
        on_delete=models.PROTECT,
        verbose_name="Тип ВС",
        related_name="audit_sheets",
    )
    captain = models.ForeignKey(
        Pilot,
        verbose_name="Командир ВС",
        on_delete=models.PROTECT,
        related_name="audits_as_captain",
    )
    first_officer = models.ForeignKey(
        Pilot,
        verbose_name="Второй пилот",
        on_delete=models.PROTECT,
        related_name="audits_as_first_officer",
    )
    second_officer = models.ForeignKey(
        Pilot,
        verbose_name="Дополнительный пилот",
        on_delete=models.PROTECT,
        related_name="audits_as_second_officer",
        null=True,
        blank=True,
    )
    flight_engineer = models.ForeignKey(
        Pilot,
        verbose_name="Бортинженер",
        on_delete=models.PROTECT,
        related_name="audits_as_flight_engineer",
        null=True,
        blank=True,
    )
    departure = models.ForeignKey(
        Airport,
        verbose_name="Аэропорт вылета",
        on_delete=models.PROTECT,
        related_name="departure_audits",
    )
    arrival = models.ForeignKey(
        Airport,
        verbose_name="Аэропорт прилёта",
        on_delete=models.PROTECT,
        related_name="arrival_audits",
    )
    working_together = models.CharField(
        "Совместная работа экипажа", max_length=1, choices=WORKING_TOGETHER_CHOICE
    )
    leg_number = models.CharField(
        "Участок полётного задания",
        max_length=10,
        choices=LEG_NUMBER_CHOICE,
        null=True,
        blank=True,
    )
    pilot_flying = models.CharField(
        "Активное управление выполняет",
        choices=PF_CHOICE,
        max_length=1,
        null=True,
        blank=True,
    )
    is_delay = models.BooleanField("Задержка вылета?", default=False)
    delay = models.PositiveIntegerField("Задержка, минут", blank=True, null=True)

    class Meta:
        verbose_name = "Лист аудита"
        verbose_name_plural = "Листы аудита"
        ordering = ["-pk"]

    def __str__(self):
        return f"Аудит № {self.audit_number}"

    captain_experience = models.PositiveIntegerField(
        "Общий стаж КВС на момент проверки",
        null=True,
        blank=True,
        help_text="Количество полных лет",
    )
    captain_type_experience = models.PositiveIntegerField(
        "Стаж КВС на типе на момент проверки",
        null=True,
        blank=True,
        help_text="Количество полных лет",
    )
    first_officer_experience = models.PositiveIntegerField(
        "Общий стаж второго пилота на момент проверки",
        null=True,
        blank=True,
        help_text="Количество полных лет",
    )
    first_officer_type_experience = models.PositiveIntegerField(
        "Стаж второго пилота на типе на момент проверки",
        null=True,
        blank=True,
        help_text="Количество полных лет",
    )
    actual_departure = models.CharField(
        "Фактический аэропорт вылета", max_length=100, blank=True, default=""
    )
    actual_arrival = models.CharField(
        "Фактический аэропорт прилёта", max_length=100, blank=True, default=""
    )
    demography_revision = models.PositiveIntegerField(
        "Версия блока демографии", default=0, editable=False
    )


class FinalMarkCrew(models.Model):
    MARK_CHOICES = [(1, "1"), (2, "2"), (3, "3"), (4, "4")]
    PREFLIGHT_BRIEF_CHOICES = [
        ("1", "Да"),
        ("2", "Нет"),
        ("3", "Не представилось возможности"),
    ]
    audit_sheet = models.OneToOneField(
        AuditSheet,
        verbose_name="Лист аудита",
        on_delete=models.CASCADE,
        related_name="final_crew_mark",
    )
    preflight_brief_with_fa = models.CharField(
        "Наблюдался ли инструктаж бортпроводников перед первым полётом?",
        max_length=1,
        choices=PREFLIGHT_BRIEF_CHOICES,
        null=True,
        blank=True,
    )
    free_communication = models.PositiveSmallIntegerField(
        "Свободное общение", choices=MARK_CHOICES, null=True, blank=True
    )
    capt_as_leader = models.PositiveSmallIntegerField(
        "КВС как руководитель", choices=MARK_CHOICES, null=True, blank=True
    )
    general_mark_capt = models.PositiveSmallIntegerField(
        "Вклад КВС в обеспечение эффективной работы экипажа",
        choices=MARK_CHOICES,
        null=True,
        blank=True,
    )
    general_mark_copilot = models.PositiveSmallIntegerField(
        "Вклад второго пилота в обеспечение эффективной работы экипажа",
        choices=MARK_CHOICES,
        null=True,
        blank=True,
    )
    total_general_mark = models.PositiveSmallIntegerField(
        "Общая оценка эффективности работы экипажа",
        choices=MARK_CHOICES,
        null=True,
        blank=True,
    )
    general_notes = models.TextField(
        "Общее впечатление о работе экипажа", blank=True, default=""
    )

    class Meta:
        verbose_name = "Итоговая оценка экипажа"
        verbose_name_plural = "Итоговые оценки экипажей"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(free_communication__isnull=True)
                | models.Q(free_communication__in=[1, 2, 3, 4]),
                name="final_crew_communication_1_4",
            ),
            models.CheckConstraint(
                condition=models.Q(capt_as_leader__isnull=True)
                | models.Q(capt_as_leader__in=[1, 2, 3, 4]),
                name="final_crew_leadership_1_4",
            ),
            models.CheckConstraint(
                condition=models.Q(general_mark_capt__isnull=True)
                | models.Q(general_mark_capt__in=[1, 2, 3, 4]),
                name="final_crew_captain_1_4",
            ),
            models.CheckConstraint(
                condition=models.Q(general_mark_copilot__isnull=True)
                | models.Q(general_mark_copilot__in=[1, 2, 3, 4]),
                name="final_crew_copilot_1_4",
            ),
            models.CheckConstraint(
                condition=models.Q(total_general_mark__isnull=True)
                | models.Q(total_general_mark__in=[1, 2, 3, 4]),
                name="final_crew_total_1_4",
            ),
        ]

    def __str__(self):
        return f"Итоговая оценка — {self.audit_sheet}"


class PhaseOfFlight(models.Model):
    PHASE_OF_FLIGHT = [
        ("preflight", "Предполетная подготовка"),
        ("taxing", "Руление"),
        ("takeoff", "Взлет"),
        ("climb", "Набор высоты"),
        ("10000_proc_up", "Пересечение 10000 футов в наборе высоты"),
        ("cruise", "Крейсерский эшелон"),
        ("descent", "Подготовка и снижение"),
        ("10000_proc_down", "Пересечение 10000 футов на снижении"),
        ("tl_proc", "Эшелон перехода"),
        ("approach", "Подход"),
        ("1000ft_stab", "Стабилизация снижения на высоте 1000 футов"),
        ("500ft_stab", "Стабилизация снижения на высоте 500 футов"),
        ("landing", "Посадка"),
        ("landing_roll", "Пробег"),
        ("parking", "Заруливание на стоянку"),
    ]
    code = models.IntegerField("Порядок сортировки", null=True, blank=True)
    phase_of_flight = models.CharField(
        "Фаза полёта", max_length=30, choices=PHASE_OF_FLIGHT, unique=True
    )

    class Meta:
        verbose_name = "Фаза полёта"
        verbose_name_plural = "Фазы полёта"
        ordering = ["code", "pk"]

    def __str__(self):
        return self.get_phase_of_flight_display()


class ChangingSafetyConditionSheet(models.Model):
    SECTION_CHOICES = [
        ("1", "Конфигурация ВС"),
        ("2", "Положение ВС на земле"),
        ("3", "Ошибки при пилотировании (на любом этапе полёта)"),
        ("4", "Заход на посадку / посадка"),
        ("5", "Прочие"),
    ]
    code = models.PositiveIntegerField(
        "Код изменения состояния безопасности ВС", unique=True
    )
    section = models.CharField("Раздел", max_length=1, choices=SECTION_CHOICES)
    name = models.CharField(
        "Описание кода изменения состояния безопасности ВС", max_length=500
    )

    class Meta:
        verbose_name = "Код изменения состояния безопасности ВС"
        verbose_name_plural = "Коды изменения состояния безопасности ВС"
        ordering = ["section", "code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class AuditMistake(models.Model):
    client_id = models.UUIDField(
        "Идентификатор наблюдения на устройстве",
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )

    MISTAKE_RELAY_CHOICE = [
        ("CAPT", "Командир ВС"),
        ("FO", "Второй пилот"),
        ("Observer", "Дополнительный пилот"),
        ("Inspector", "Проверяющий"),
        ("FE", "Бортинженер"),
        ("Auditor", "Аудитор LOSA"),
        ("Nobody", "Никто"),
        ("atc", "Служба ОрВД"),
        ("handling", "Команда наземного обслуживания"),
        ("FA", "Бортпроводник"),
        ("maintenance_group", "ТОиР"),
        ("Aircraft_systems", "Системы ВС"),
        ("Others", "Другие"),
    ]
    REACTION_CHOICE = [("1", "Захват"), ("2", "Раздражение"), ("3", "Невосприятие")]
    ERROR_RESULT_CHOICE = [
        ("1", "Отсутствие последствий"),
        ("2", "Изменение состояния безопасности ВС"),
        ("3", "Дополнительная ошибка"),
    ]
    CHANGING_RESULT_CHOICE = [
        ("1", "Отсутствие последствий"),
        ("2", "Дополнительная ошибка"),
    ]
    audit_sheet = models.ForeignKey(
        AuditSheet,
        verbose_name="Лист аудита",
        on_delete=models.CASCADE,
        related_name="mistake_events",
    )
    mistake = models.ForeignKey(
        Mistake, verbose_name="Ошибка", on_delete=models.PROTECT, related_name="events"
    )
    observed_at = models.DateTimeField("Время наблюдения", null=True, blank=True)
    flight_phase = models.ForeignKey(
        PhaseOfFlight,
        verbose_name="Фаза полёта",
        on_delete=models.PROTECT,
        related_name="mistake_events",
    )
    who_made = models.CharField(
        "Кто допустил ошибку?",
        max_length=30,
        choices=MISTAKE_RELAY_CHOICE,
        null=True,
        blank=True,
    )
    who_noticed = models.CharField(
        "Кто заметил ошибку?",
        max_length=30,
        choices=MISTAKE_RELAY_CHOICE,
        null=True,
        blank=True,
    )
    reaction = models.CharField(
        "Реакция экипажа на ошибку",
        max_length=1,
        choices=REACTION_CHOICE,
        null=True,
        blank=True,
    )
    error_result = models.CharField(
        "Результат ошибки",
        max_length=1,
        choices=ERROR_RESULT_CHOICE,
        null=True,
        blank=True,
    )
    for_threat_reason = models.ForeignKey(
        "AuditThreat",
        verbose_name="Угроза, повлиявшая на ошибку",
        on_delete=models.PROTECT,
        related_name="influenced_mistakes",
        null=True,
        blank=True,
    )
    is_action_ok = models.BooleanField(
        "Были ли действия экипажа в связи с ошибкой удачными?",
        null=True,
        blank=True,
        default=None,
    )
    code_csc = models.ForeignKey(
        ChangingSafetyConditionSheet,
        verbose_name="Изменение состояния безопасности ВС",
        on_delete=models.PROTECT,
        related_name="mistake_events",
        null=True,
        blank=True,
    )
    who_identified_changing = models.CharField(
        "Кто определил изменение состояния безопасности ВС?",
        max_length=30,
        choices=MISTAKE_RELAY_CHOICE,
        null=True,
        blank=True,
    )
    crew_reaction = models.CharField(
        "Реакция экипажа на изменение состояния безопасности ВС",
        max_length=1,
        choices=REACTION_CHOICE,
        null=True,
        blank=True,
    )
    changing_result = models.CharField(
        "Результат изменения состояния безопасности ВС",
        max_length=1,
        choices=CHANGING_RESULT_CHOICE,
        null=True,
        blank=True,
    )
    comment = models.TextField("Комментарий", blank=True)

    class Meta:
        verbose_name = "Случай ошибки"
        verbose_name_plural = "Случаи ошибок"
        ordering = ["observed_at", "pk"]

    def __str__(self):
        return f"Аудит № {self.audit_sheet.audit_number}: ошибка {self.mistake.code}, запись {self.pk}"


class AuditSafetyCondition(models.Model):
    REACTION_CHOICES = [("1", "Захват"), ("2", "Раздражение"), ("3", "Невосприятие")]
    RESULT_CHOICES = [("1", "Отсутствие последствий"), ("2", "Дополнительная ошибка")]
    audit_sheet = models.ForeignKey(
        AuditSheet,
        verbose_name="Лист аудита",
        on_delete=models.CASCADE,
        related_name="safety_condition_events",
    )
    condition = models.ForeignKey(
        ChangingSafetyConditionSheet,
        verbose_name="Изменение состояния безопасности ВС",
        on_delete=models.PROTECT,
        related_name="events",
    )
    observed_at = models.DateTimeField("Время наблюдения", null=True, blank=True)
    flight_phase = models.ForeignKey(
        PhaseOfFlight,
        verbose_name="Фаза полёта",
        on_delete=models.PROTECT,
        related_name="safety_condition_events",
    )
    mistakes = models.ManyToManyField(
        AuditMistake,
        verbose_name="Связанные случаи ошибок",
        related_name="safety_condition_events",
        blank=True,
    )
    who_identified = models.CharField(
        "Кто определил изменение?",
        max_length=30,
        choices=AuditMistake.MISTAKE_RELAY_CHOICE,
        null=True,
        blank=True,
    )
    crew_reaction = models.CharField(
        "Реакция экипажа на изменение",
        max_length=1,
        choices=REACTION_CHOICES,
        null=True,
        blank=True,
    )
    result = models.CharField(
        "Результат изменения",
        max_length=1,
        choices=RESULT_CHOICES,
        null=True,
        blank=True,
    )
    comment = models.TextField("Комментарий", blank=True)

    class Meta:
        verbose_name = "Случай изменения состояния безопасности ВС"
        verbose_name_plural = "Изменения состояния безопасности ВС"
        ordering = ["observed_at", "pk"]

    def __str__(self):
        return f"Аудит № {self.audit_sheet.audit_number}: изменение {self.condition.code}, запись {self.pk}"


class AuditThreat(models.Model):
    client_id = models.UUIDField(
        "Идентификатор наблюдения на устройстве",
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )

    audit_sheet = models.ForeignKey(
        AuditSheet,
        verbose_name="Лист аудита",
        on_delete=models.CASCADE,
        related_name="threat_events",
    )
    threat = models.ForeignKey(
        Threat,
        verbose_name="Тип угрозы",
        on_delete=models.PROTECT,
        related_name="events",
    )
    observed_at = models.DateTimeField("Время наблюдения", null=True, blank=True)
    flight_phase = models.ForeignKey(
        PhaseOfFlight,
        verbose_name="Фаза полёта",
        on_delete=models.PROTECT,
        related_name="threat_events",
    )
    comment = models.TextField("Комментарий", blank=True)
    was_control_effective = models.BooleanField(
        "Был ли контроль за ФУ эффективным?", null=True, blank=True, default=None
    )
    correct_actions = models.BooleanField(
        "Были ли действия экипажа по контролю за ФУ правильными?",
        null=True,
        blank=True,
        default=None,
    )

    class Meta:
        verbose_name = "Случай угрозы"
        verbose_name_plural = "Случаи угроз"
        ordering = ["observed_at", "pk"]

    def __str__(self):
        return f"Аудит № {self.audit_sheet.audit_number}: угроза {self.threat.code}, запись {self.pk}"


class AssessmentStage(models.Model):
    template = models.ForeignKey(
        "AssessmentTemplate",
        verbose_name="Шаблон критериев",
        on_delete=models.PROTECT,
        related_name="assessment_stages",
        null=True,
        blank=True,
    )
    code = models.CharField("Код", max_length=30, unique=True)
    name = models.CharField("Название", max_length=200)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Этап оценки"
        verbose_name_plural = "Этапы оценки"
        ordering = ["sort_order", "pk"]

    def __str__(self):
        return self.name


class AssessmentTemplate(models.Model):
    name = models.CharField("Название", max_length=100)
    version = models.CharField("Версия", max_length=20, unique=True)

    class Meta:
        verbose_name = "Шаблон оценки"
        verbose_name_plural = "Шаблоны оценки"
        ordering = ["pk"]

    def __str__(self):
        return f"{self.name} — версия {self.version}"


class AssessmentSection(models.Model):
    template = models.ForeignKey(
        AssessmentTemplate,
        verbose_name="Шаблон",
        on_delete=models.PROTECT,
        related_name="sections",
    )
    number = models.PositiveSmallIntegerField("Номер раздела")
    name = models.CharField("Название", max_length=300)

    class Meta:
        verbose_name = "Раздел оценки"
        verbose_name_plural = "Разделы оценки"
        ordering = ["number", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "number"], name="unique_assessment_section"
            )
        ]

    def __str__(self):
        return f"{self.number}. {self.name}"


class AssessmentCriterion(models.Model):
    section = models.ForeignKey(
        AssessmentSection,
        verbose_name="Раздел",
        on_delete=models.PROTECT,
        related_name="criteria",
    )
    code = models.CharField("Код", max_length=10)
    name = models.CharField("Название", max_length=300)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Критерий оценки"
        verbose_name_plural = "Критерии оценки"
        ordering = ["section__number", "sort_order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["section", "code"], name="unique_assessment_criterion"
            )
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"


class AuditAssessment(models.Model):
    audit_sheet = models.ForeignKey(
        AuditSheet,
        verbose_name="Лист аудита",
        on_delete=models.CASCADE,
        related_name="assessments",
    )
    stage = models.ForeignKey(
        AssessmentStage,
        verbose_name="Этап оценки",
        on_delete=models.PROTECT,
        related_name="assessments",
    )
    facts = models.TextField("Изложение фактов", blank=True)

    class Meta:
        verbose_name = "Изложение фактов по этапу"
        verbose_name_plural = "Изложения фактов по этапам"
        ordering = ["stage__sort_order", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["audit_sheet", "stage"], name="unique_audit_assessment_stage"
            )
        ]

    def __str__(self):
        return f"{self.audit_sheet} — {self.stage}"


class AuditCriterionRating(models.Model):
    SCORE_CHOICES = [(1, "1"), (2, "2"), (3, "3"), (4, "4")]
    audit_sheet = models.ForeignKey(
        AuditSheet,
        verbose_name="Лист аудита",
        on_delete=models.CASCADE,
        related_name="criterion_ratings",
    )
    criterion = models.ForeignKey(
        AssessmentCriterion,
        verbose_name="Критерий оценки",
        on_delete=models.PROTECT,
        related_name="audit_ratings",
    )
    stage = models.ForeignKey(
        AssessmentStage,
        verbose_name="Этап оценки",
        on_delete=models.PROTECT,
        related_name="criterion_ratings",
    )
    score = models.PositiveSmallIntegerField(
        "Оценка", choices=SCORE_CHOICES, null=True, blank=True
    )
    comment = models.TextField("Комментарий", blank=True)

    class Meta:
        verbose_name = "Оценка работы экипажа"
        verbose_name_plural = "Оценки работы экипажа"
        ordering = [
            "stage__sort_order",
            "criterion__section__number",
            "criterion__sort_order",
            "pk",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["audit_sheet", "stage", "criterion"],
                name="unique_sheet_stage_criterion",
            ),
            models.CheckConstraint(
                condition=models.Q(score__isnull=True)
                | models.Q(score__in=[1, 2, 3, 4]),
                name="criterion_rating_score_1_to_4",
            ),
        ]

    def __str__(self):
        return (
            f"{self.audit_sheet} — {self.stage} — {self.criterion.code}: {self.score}"
        )


class TypeApproachAndWeather(models.Model):
    APPROACH_TYPE_CHOICES = [
        ("ILS", "ILS"),
        ("VIS", "Визуальный"),
        ("RNAV", "RNAV"),
        ("VOR/Loc", "VOR/Loc"),
        ("LNAV/VNAV", "LNAV/VNAV"),
        ("NDB", "NDB"),
    ]
    VISUAL_CONDITION_CHOICES = [
        ("VMC", "Визуальные условия"),
        ("IMC", "Инструментальные условия"),
    ]

    audit_sheet = models.OneToOneField(
        AuditSheet,
        verbose_name="Лист аудита",
        on_delete=models.CASCADE,
        related_name="approach_conditions",
    )
    approach_type = models.CharField(
        "Тип захода на посадку", max_length=20, choices=APPROACH_TYPE_CHOICES
    )
    visual_condition = models.CharField(
        "Погодные условия",
        max_length=20,
        choices=VISUAL_CONDITION_CHOICES,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Тип захода и погодные условия"
        verbose_name_plural = "Типы захода и погодные условия"

    def __str__(self):
        weather = (
            self.get_visual_condition_display()
            if self.visual_condition
            else "погода не указана"
        )
        return f"{self.get_approach_type_display()} — {weather}"


class DescentApproach(models.Model):
    YES_NO_CHOICES = [
        ("1", "Да"),
        ("2", "Нет"),
    ]

    TRAJECTORY_CHOICES = [
        ("1", "Нормально"),
        ("2", "Значительно выше"),
        ("3", "Значительно ниже"),
    ]

    START_OF_DESCENT_CHOICES = [
        ("before", "Раньше точки TOD"),
        ("at", "В точке TOD"),
        ("after", "Позже точки TOD"),
    ]

    APPROACH_MODE_CHOICES = [
        ("man", "Ручное"),
        ("auto", "Автопилот"),
    ]

    FLAP_SETTINGS_CHOICES = [
        (
            "1",
            "На скорости, близкой к минимальной эволютивной "
            "или равной ей",
        ),
        (
            "2",
            "На скорости, близкой к максимальной для выпуска "
            "закрылков или равной ей",
        ),
        ("3", "На скорости выше максимальной для выпуска закрылков"),
    ]

    audit_sheet = models.OneToOneField(
        AuditSheet,
        verbose_name="Лист аудита",
        on_delete=models.CASCADE,
        related_name="descent_approach",
    )
    ten_thousand_brief = models.CharField(
        "Был ли проведён инструктаж по снижению до точки TOD?",
        max_length=1,
        choices=YES_NO_CHOICES,
        null=True,
        blank=True,
    )
    start_of_descent = models.CharField(
        "Начало снижения относительно точки TOD, рассчитанной FMS",
        max_length=6,
        choices=START_OF_DESCENT_CHOICES,
        null=True,
        blank=True,
    )
    descent_trajectory = models.CharField(
        "Положение относительно траектории снижения FMS "
        "или стандартной траектории",
        max_length=1,
        choices=TRAJECTORY_CHOICES,
        null=True,
        blank=True,
    )
    describe_deviation = models.TextField(
        "При отклонении опишите причину и действия экипажа "
        "по возвращению на требуемую траекторию",
        blank=True,
        default="",
    )
    approach_mode = models.CharField(
        "Заход на посадку: тип управления",
        max_length=4,
        choices=APPROACH_MODE_CHOICES,
        null=True,
        blank=True,
    )
    flap_settings = models.CharField(
        "Скорость при выпуске закрылков",
        max_length=1,
        choices=FLAP_SETTINGS_CHOICES,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Снижение и заход на посадку"
        verbose_name_plural = "Снижение и заход на посадку"
        ordering = ["-pk"]

    def __str__(self):
        return f"{self.audit_sheet} — снижение и заход"

class StabilizedApproachAssessment(models.Model):
    STAGE_CHOICES = [
        ("glideslope_entry", "Вход в глиссаду"),
        ("1000_ft", "Пересечение 1000 футов"),
        ("500_ft", "Пересечение 500 футов"),
    ]

    RATE_CHOICES = [
        ("1", "Превышение 1000 фут/мин не наблюдалось"),
        ("2", "Скорость снижения более 1000 фут/мин"),
    ]

    THRUST_CHOICES = [
        ("1", "Требуемый режим двигателей выдержан"),
        ("2", "Режим двигателей не соответствует требуемому"),
        ("3", "Частое изменение режима двигателей — раскачка по тяге"),
    ]

    LANDING_CONFIG_CHOICES = [
        ("1", "Закрылки полностью выпущены, шасси выпущены"),
        ("2", "Закрылки выпущены не полностью, шасси выпущены"),
        ("3", "Закрылки не выпущены, шасси выпущены"),
        ("4", "Закрылки не выпущены, шасси не выпущены"),
    ]

    audit_sheet = models.ForeignKey(
        AuditSheet,
        verbose_name="Лист аудита",
        on_delete=models.CASCADE,
        related_name="stabilized_approach_assessments",
    )
    stage = models.CharField(
        "Этап",
        max_length=20,
        choices=STAGE_CHOICES,
    )
    speed_deviation = models.IntegerField(
        "Отклонение скорости",
        null=True,
        blank=True,
        help_text=(
            "В узлах: положительное или отрицательное число, "
            "например +10 или -5."
        ),
    )
    rate_of_descent_deviation = models.CharField(
        "Скорость снижения при стандартной глиссаде",
        max_length=1,
        choices=RATE_CHOICES,
        null=True,
        blank=True,
    )
    thrust_settings = models.CharField(
        "Режим двигателей",
        max_length=1,
        choices=THRUST_CHOICES,
        null=True,
        blank=True,
    )
    landing_config = models.CharField(
        "Посадочная конфигурация ВС",
        max_length=1,
        choices=LANDING_CONFIG_CHOICES,
        null=True,
        blank=True,
    )
    course_deviation = models.DecimalField(
        "Отклонение от линии курса, dot",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    course_more_than = models.BooleanField(
        "По курсу: более указанного значения",
        default=False,
    )
    glideslope_deviation = models.DecimalField(
        "Отклонение от глиссады, dot",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    glideslope_more_than = models.BooleanField(
        "По глиссаде: более указанного значения",
        default=False,
    )
    comment = models.TextField(
        "Комментарий",
        blank=True,
    )

    class Meta:
        verbose_name = "Оценка стабилизированного захода"
        verbose_name_plural = "Оценки стабилизированного захода"
        ordering = ["audit_sheet_id", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["audit_sheet", "stage"],
                name="unique_stabilized_approach_stage",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(course_deviation__isnull=True)
                    | models.Q(course_deviation__gte=0)
                ),
                name="approach_course_dot_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(glideslope_deviation__isnull=True)
                    | models.Q(glideslope_deviation__gte=0)
                ),
                name="approach_glideslope_dot_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(course_more_than=False)
                    | models.Q(course_deviation__isnull=False)
                ),
                name="approach_course_more_requires_value",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(glideslope_more_than=False)
                    | models.Q(glideslope_deviation__isnull=False)
                ),
                name="approach_glide_more_requires_value",
            ),
        ]

    def __str__(self):
        return f"{self.audit_sheet} — {self.get_stage_display()}"


class Landing(models.Model):
    THRESHOLD_HEIGHT_CHOICES = [
        ("1", "Нормальная"),
        ("2", "Отклонение вверх"),
        ("3", "Отклонение вниз"),
    ]

    FLARE_TOUCH_CHOICES = [
        ("1", "В посадочные знаки — нормально"),
        ("2", "До посадочных знаков — недолёт"),
        ("3", "После посадочных знаков — перелёт"),
    ]

    G_LOAD_CHOICES = [
        ("1", "Нормально"),
        ("2", "Мягко"),
        ("3", "Грубо"),
    ]

    audit_sheet = models.OneToOneField(
        AuditSheet,
        verbose_name="Лист аудита",
        on_delete=models.CASCADE,
        related_name="landing_assessment",
    )
    threshold_height = models.CharField(
        "Высота пролёта порога ВПП относительно 50 футов",
        max_length=1,
        choices=THRESHOLD_HEIGHT_CHOICES,
        null=True,
        blank=True,
    )
    flare_and_touch_distance = models.CharField(
        "Место касания относительно посадочных знаков",
        max_length=1,
        choices=FLARE_TOUCH_CHOICES,
        null=True,
        blank=True,
    )
    g_load = models.CharField(
        "Субъективная оценка касания",
        max_length=1,
        choices=G_LOAD_CHOICES,
        null=True,
        blank=True,
        help_text="Оценка аудитора без объективных данных о перегрузке.",
    )

    class Meta:
        verbose_name = "Оценка посадки"
        verbose_name_plural = "Оценки посадки"
        ordering = ["-pk"]

    def __str__(self):
        return f"{self.audit_sheet} — посадка"


class RolloutAndTaxingAndParking(models.Model):
    REVERSER_ON_CHOICES = [
        ("1", "Включение по технологии"),
        ("2", "Включение до касания"),
        ("3", "Позднее, неэффективное включение"),
        ("4", "Реверс не использовался"),
        ("5", "Включение не по технологии, без ожидания открытия створок"),
    ]

    REVERSER_OFF_CHOICES = [
        ("1", "Выключение по технологии"),
        ("2", "Выключение без фиксации малого реверса, одним движением"),
        ("3", "Максимальный реверс не выключен на малых скоростях"),
    ]

    TAXI_SPEED_CHOICES = [
        ("1", "Нормальная"),
        ("2", "Повышенная"),
        ("3", "Пониженная"),
    ]

    PARKING_CHOICES = [
        ("1", "По командам системы или встречающего"),
        ("2", "С небольшими отклонениями от места парковки"),
        ("3", "С большими отклонениями от места парковки"),
    ]

    audit_sheet = models.OneToOneField(
        AuditSheet,
        verbose_name="Лист аудита",
        on_delete=models.CASCADE,
        related_name="rollout_taxing_assessment",
    )
    thrust_reverser_on = models.CharField(
        "Включение реверса тяги",
        max_length=1,
        choices=REVERSER_ON_CHOICES,
        null=True,
        blank=True,
    )
    thrust_reverser_off = models.CharField(
        "Выключение реверса тяги",
        max_length=1,
        choices=REVERSER_OFF_CHOICES,
        null=True,
        blank=True,
    )
    taxi_speed = models.CharField(
        "Скорость руления по прямой",
        max_length=1,
        choices=TAXI_SPEED_CHOICES,
        null=True,
        blank=True,
    )
    taxi_speed_turn = models.CharField(
        "Скорость руления на разворотах",
        max_length=1,
        choices=TAXI_SPEED_CHOICES,
        null=True,
        blank=True,
    )
    parking = models.CharField(
        "Заруливание на стоянку",
        max_length=1,
        choices=PARKING_CHOICES,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Пробег, руление и стоянка"
        verbose_name_plural = "Оценки пробега, руления и стоянки"
        ordering = ["-pk"]

    def __str__(self):
        return f"{self.audit_sheet} — пробег, руление и стоянка"