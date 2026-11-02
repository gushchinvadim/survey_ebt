from .models import (
    Aircraft,
    Airport,
    AuditMistake,
    Auditor,
    AuditSheet,
    AuditThreat,
    Company,
    Location,
    Mistake,
    PhaseOfFlight,
    Pilot,
    Threat,
    AssessmentSection,
    AssessmentCriterion,
    AssessmentTemplate,
    AuditAssessment,
    AuditCriterionRating,
    AssessmentStage,
    StabilizedApproachAssessment, MistakeType, MistakeSection, ChangingSafetyConditionSheet, AuditSafetyCondition,
    TypeApproachAndWeather, FinalMarkCrew, DescentApproach, Landing, RolloutAndTaxingAndParking,
)
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.core.management import call_command, CommandError
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("id", "location_name", "location_code", "address")
    search_fields = ("location_name", "location_code", "address")


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("id", "company_name", "company_code")
    search_fields = ("company_name", "company_code")


@admin.register(Pilot)
class PilotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "pilot_id",
        "company",
        "location",
        "position",
        "experience",
        "type_experience",
        "fmc_experience",
    )
    search_fields = ("=pilot_id", "company__company_code", "company__company_name")
    list_filter = ("company", "location", "position")
    autocomplete_fields = ("company", "location")
    list_select_related = ("company", "location")


@admin.register(Auditor)
class AuditorAdmin(admin.ModelAdmin):
    list_display = ("id", "auditor_code", "name")
    search_fields = ("name", "=auditor_code")
    ordering = ("name", "pk")


@admin.register(Aircraft)
class AircraftAdmin(admin.ModelAdmin):
    list_display = ("id", "aircraft_type")
    search_fields = ("aircraft_type",)


@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    list_display = ("id", "airport_code", "airport_name")
    search_fields = ("airport_code", "airport_name")


class MistakeExcelImportForm(forms.Form):
    file = forms.FileField(
        label="Excel-файл",
        help_text="Формат .xlsx. Колонки: code, name, type_code, section.",
    )
    sheet = forms.CharField(
        label="Название листа",
        required=False,
        help_text="Оставь пустым для активного листа.",
    )
    dry_run = forms.BooleanField(
        label="Только проверить, без сохранения",
        required=False,
        initial=True,
    )

    def clean_file(self):
        uploaded = self.cleaned_data["file"]

        if Path(uploaded.name).suffix.lower() != ".xlsx":
            raise forms.ValidationError("Выбери файл в формате .xlsx.")

        return uploaded


@admin.register(ChangingSafetyConditionSheet)
class ChangingSafetyConditionSheetAdmin(admin.ModelAdmin):
    list_display = ("code", "section", "name")
    search_fields = ("=code", "name")
    list_filter = ("section",)

    change_list_template = (
        "admin/losa/changingsafetyconditionsheet/change_list.html"
    )

    def can_import(self, request):
        return (
            self.has_add_permission(request)
            and self.has_change_permission(request)
        )

    def get_urls(self):
        custom_urls = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel),
                name="losa_changingsafetyconditionsheet_import_excel",
            ),
        ]
        return custom_urls + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        context = dict(extra_context or {})
        context["can_import"] = self.can_import(request)
        return super().changelist_view(request, extra_context=context)

    def import_excel(self, request):
        if not self.can_import(request):
            raise PermissionDenied

        form = SafetyConditionExcelImportForm(
            request.POST if request.method == "POST" else None,
            request.FILES if request.method == "POST" else None,
        )

        if request.method == "POST" and form.is_valid():
            output = StringIO()

            try:
                with TemporaryDirectory() as directory:
                    file_path = Path(directory) / "safety_conditions.xlsx"

                    with file_path.open("wb") as destination:
                        for chunk in form.cleaned_data["file"].chunks():
                            destination.write(chunk)

                    call_command(
                        "load_safety_conditions_excel",
                        str(file_path),
                        sheet=form.cleaned_data["sheet"] or None,
                        dry_run=form.cleaned_data["dry_run"],
                        stdout=output,
                        no_color=True,
                    )

            except (CommandError, OSError) as exc:
                form.add_error(None, str(exc))
            else:
                self.message_user(
                    request,
                    output.getvalue().strip() or "Загрузка завершена.",
                    level=messages.SUCCESS,
                )
                return redirect(reverse(
                    "admin:losa_changingsafetyconditionsheet_changelist",
                    current_app=self.admin_site.name,
                ))

        request.current_app = self.admin_site.name

        context = {
            **self.admin_site.each_context(request),
            "title": "Загрузить коды изменения состояния безопасности ВС",
            "opts": self.model._meta,
            "form": form,
            "changelist_url": reverse(
                "admin:losa_changingsafetyconditionsheet_changelist",
                current_app=self.admin_site.name,
            ),
        }

        return TemplateResponse(
            request,
            "admin/losa/changingsafetyconditionsheet/import_excel.html",
            context,
        )


class AuditSafetyConditionForm(forms.ModelForm):
    class Meta:
        model = AuditSafetyCondition
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()

        sheet = cleaned.get("audit_sheet")
        if sheet is None and self.instance.audit_sheet_id:
            sheet = self.instance.audit_sheet

        mistakes = cleaned.get("mistakes")

        if sheet and mistakes is not None:
            if any(event.audit_sheet_id != sheet.pk for event in mistakes):
                self.add_error(
                    "mistakes",
                    "Все связанные ошибки должны относиться к этому листу.",
                )

        return cleaned

@admin.register(MistakeType)
class MistakeTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "describe")
    search_fields = ("code", "name", "describe")

@admin.register(MistakeSection)
class MistakeSectionAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "sort_order")
    search_fields = ("name", "type__name", "type__code")
    list_filter = ("type",)
    autocomplete_fields = ("type",)
    list_select_related = ("type",)

@admin.register(Mistake)
class MistakeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "type", "section_name")
    search_fields = ("code", "name", "section__name")
    list_filter = ("type", "section")
    autocomplete_fields = ("type", "section")
    list_select_related = ("type", "section")

    @admin.display(
        description="Раздел",
        ordering="section__name",
    )
    def section_name(self, obj):
        return obj.section.name if obj.section_id else "—"

    change_list_template = "admin/losa/mistake/change_list.html"

    def can_import(self, request):
        return (
            self.has_add_permission(request)
            and self.has_change_permission(request)
        )

    def get_urls(self):
        custom_urls = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel),
                name="losa_mistake_import_excel",
            ),
        ]
        return custom_urls + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        context = dict(extra_context or {})
        context["can_import"] = self.can_import(request)
        return super().changelist_view(request, extra_context=context)

    def import_excel(self, request):
        if not self.can_import(request):
            raise PermissionDenied

        form = MistakeExcelImportForm(
            request.POST if request.method == "POST" else None,
            request.FILES if request.method == "POST" else None,
        )

        if request.method == "POST" and form.is_valid():
            output = StringIO()

            try:
                with TemporaryDirectory() as directory:
                    file_path = Path(directory) / "mistakes.xlsx"

                    with file_path.open("wb") as destination:
                        for chunk in form.cleaned_data["file"].chunks():
                            destination.write(chunk)

                    call_command(
                        "load_mistakes_excel",
                        str(file_path),
                        sheet=form.cleaned_data["sheet"] or None,
                        dry_run=form.cleaned_data["dry_run"],
                        stdout=output,
                        no_color=True,
                    )

            except (CommandError, OSError) as exc:
                form.add_error(None, str(exc))
            else:
                self.message_user(
                    request,
                    output.getvalue().strip() or "Загрузка завершена.",
                    level=messages.SUCCESS,
                )
                return redirect(reverse(
                    "admin:losa_mistake_changelist",
                    current_app=self.admin_site.name,
                ))

        request.current_app = self.admin_site.name

        context = {
            **self.admin_site.each_context(request),
            "title": "Загрузить ошибки из Excel",
            "opts": self.model._meta,
            "form": form,
            "changelist_url": reverse(
                "admin:losa_mistake_changelist",
                current_app=self.admin_site.name,
            ),
        }

        return TemplateResponse(
            request,
            "admin/losa/mistake/import_excel.html",
            context,
        )


class ThreatExcelImportForm(forms.Form):
    file = forms.FileField(
        label="Excel-файл", help_text="Формат .xlsx. Колонки: code, type, describe."
    )
    sheet = forms.CharField(
        label="Название листа",
        required=False,
        help_text="Оставь пустым для первого активного листа.",
    )
    dry_run = forms.BooleanField(
        label="Только проверить, без сохранения", required=False, initial=True
    )

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if Path(uploaded.name).suffix.lower() != ".xlsx":
            raise forms.ValidationError("Выбери файл в формате .xlsx.")
        return uploaded


@admin.register(Threat)
class ThreatAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "type", "describe")
    search_fields = ("code", "describe")
    list_filter = ("type",)
    change_list_template = "admin/losa/threat/change_list.html"

    def can_import(self, request):
        return self.has_add_permission(request) and self.has_change_permission(request)

    def get_urls(self):
        custom_urls = [
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel),
                name="losa_threat_import_excel",
            )
        ]
        return custom_urls + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        context = dict(extra_context or {})
        context["can_import"] = self.can_import(request)
        return super().changelist_view(request, extra_context=context)

    def import_excel(self, request):
        if not self.can_import(request):
            raise PermissionDenied
        form = ThreatExcelImportForm(
            request.POST if request.method == "POST" else None,
            request.FILES if request.method == "POST" else None,
        )
        if request.method == "POST" and form.is_valid():
            output = StringIO()
            try:
                with TemporaryDirectory() as directory:
                    file_path = Path(directory) / "threats.xlsx"
                    with file_path.open("wb") as destination:
                        for chunk in form.cleaned_data["file"].chunks():
                            destination.write(chunk)
                    call_command(
                        "load_exel",
                        str(file_path),
                        sheet=form.cleaned_data["sheet"] or None,
                        dry_run=form.cleaned_data["dry_run"],
                        stdout=output,
                        no_color=True,
                    )
            except (CommandError, OSError) as exc:
                form.add_error(None, str(exc))
            else:
                self.message_user(
                    request,
                    output.getvalue().strip() or "Загрузка завершена.",
                    level=messages.SUCCESS,
                )
                return redirect(
                    reverse(
                        "admin:losa_threat_changelist", current_app=self.admin_site.name
                    )
                )
        context = {
            **self.admin_site.each_context(request),
            "title": "Загрузить факторы угроз из Excel",
            "opts": self.model._meta,
            "form": form,
            "changelist_url": reverse(
                "admin:losa_threat_changelist", current_app=self.admin_site.name
            ),
        }
        request.current_app = self.admin_site.name
        return TemplateResponse(request, "admin/losa/threat/import_excel.html", context)


@admin.register(PhaseOfFlight)
class PhaseOfFlightAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "phase_label")
    search_fields = ("phase_of_flight",)
    ordering = ("code", "pk")

    @admin.display(description="Фаза полёта", ordering="phase_of_flight")
    def phase_label(self, obj):
        return obj.get_phase_of_flight_display()


class AuditMistakeInline(admin.TabularInline):
    model = AuditMistake
    fields = ("mistake", "observed_at", "flight_phase", "comment")
    autocomplete_fields = ("mistake", "flight_phase")
    extra = 0
    show_change_link = True

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("audit_sheet", "mistake", "flight_phase")
        )


class AuditThreatInline(admin.TabularInline):
    model = AuditThreat
    fields = (
        "threat",
        "observed_at",
        "flight_phase",
        "was_control_effective",
        "correct_actions",
        "comment",
    )
    autocomplete_fields = ("threat", "flight_phase")
    extra = 0
    show_change_link = True

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("audit_sheet", "threat", "flight_phase")
        )


class AssessmentSectionInline(admin.TabularInline):
    model = AssessmentSection
    fields = ("number", "name")
    extra = 0
    show_change_link = True


@admin.register(AssessmentTemplate)
class AssessmentTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "version")
    search_fields = ("name", "version")
    inlines = (AssessmentSectionInline,)


class AssessmentCriterionInline(admin.TabularInline):
    model = AssessmentCriterion
    fields = ("code", "name", "sort_order")
    extra = 0


@admin.register(AssessmentSection)
class AssessmentSectionAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "template")
    search_fields = ("name", "template__name")
    list_filter = ("template",)
    list_select_related = ("template",)
    inlines = (AssessmentCriterionInline,)


@admin.register(AuditAssessment)
class AuditAssessmentAdmin(admin.ModelAdmin):
    @admin.display(description="Анализ текста")
    def analysis_link(self, obj):
        if not obj or not obj.pk:
            return 'Сначала сохраните исходный текст.'
        return format_html('<a href="{}">Разобрать для аналитики</a>',
                           reverse('admin:text-analysis-stage', args=[obj.pk]))

    readonly_fields = ("analysis_link",)
    list_display = ("audit_sheet", "stage", "analysis_link")
    search_fields = ("audit_sheet__audit_number",)
    list_filter = ("stage",)
    list_select_related = ("audit_sheet", "stage")
    fields = ("audit_sheet", "stage", "facts", "analysis_link")
    autocomplete_fields = ("audit_sheet", "stage")


class AuditAssessmentInline(admin.TabularInline):
    analysis_link = AuditAssessmentAdmin.analysis_link
    readonly_fields = ("analysis_link",)
    model = AuditAssessment
    fields = ("stage", "facts", "analysis_link")
    extra = 0
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("audit_sheet", "stage")

    autocomplete_fields = ("stage",)
    max_num = 4


class AuditCriterionRatingInline(admin.TabularInline):
    model = AuditCriterionRating
    fields = ("stage", "criterion", "score", "comment")
    autocomplete_fields = ("stage", "criterion")
    extra = 0

    def get_queryset(self, request):
        return (
            super().get_queryset(request).select_related("stage", "criterion__section")
        )


class StabilizedApproachAssessmentInline(admin.StackedInline):
    model = StabilizedApproachAssessment
    extra = 0
    max_num = 3
    show_change_link = True

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "stage",
                    "speed_deviation",
                    "rate_of_descent_deviation",
                    "thrust_settings",
                    "landing_config",
                    ("course_deviation", "course_more_than"),
                    ("glideslope_deviation", "glideslope_more_than"),
                    "comment",
                ),
            },
        ),
    )



class AuditSafetyConditionInline(admin.StackedInline):
    model = AuditSafetyCondition
    form = AuditSafetyConditionForm
    extra = 0

    autocomplete_fields = (
        "condition",
        "flight_phase",
        "mistakes",
    )

    fieldsets = (
        ("Наблюдение", {
            "fields": (
                "condition",
                "observed_at",
                "flight_phase",
                "mistakes",
            ),
        }),
        ("Действия экипажа", {
            "fields": (
                "who_identified",
                "crew_reaction",
                "result",
                "comment",
            ),
        }),
    )

class TypeApproachAndWeatherInline(admin.StackedInline):
    model = TypeApproachAndWeather
    fields = ("approach_type", "visual_condition")
    extra = 1
    max_num = 1

@admin.register(TypeApproachAndWeather)
class TypeApproachAndWeatherAdmin(admin.ModelAdmin):
    list_display = ("audit_sheet", "approach_type", "visual_condition")
    search_fields = ("audit_sheet__audit_number",)
    list_filter = ("approach_type", "visual_condition")
    autocomplete_fields = ("audit_sheet",)
    list_select_related = ("audit_sheet",)

@admin.register(FinalMarkCrew)
class FinalMarkCrewAdmin(admin.ModelAdmin):
    @admin.display(description="Анализ текста")
    def analysis_link(self, obj):
        if not obj or not obj.pk:
            return 'Сначала сохраните исходный текст.'
        return format_html('<a href="{}">Разобрать для аналитики</a>',
                           reverse('admin:text-analysis-final', args=[obj.pk]))

    readonly_fields = ("analysis_link",)
    list_display = (
        "audit_sheet",
        "free_communication",
        "capt_as_leader",
        "general_mark_capt",
        "general_mark_copilot",
        "total_general_mark",
    )
    search_fields = (
        "audit_sheet__audit_number",
        "general_notes",
    )
    list_filter = (
        "preflight_brief_with_fa",
        "total_general_mark",
    )
    autocomplete_fields = ("audit_sheet",)
    list_select_related = ("audit_sheet",)

    fieldsets = (
        ("Проверка", {
            "fields": ("audit_sheet",),
        }),
        ("Инструктаж", {
            "fields": ("preflight_brief_with_fa",),
        }),
        ("Работа экипажа", {
            "fields": (
                "free_communication",
                "capt_as_leader",
                "general_mark_capt",
                "general_mark_copilot",
                "total_general_mark",
            ),
        }),
        ("Общее впечатление", {
            "fields": ("general_notes", "analysis_link"),
        }),
    )

class FinalMarkCrewInline(admin.StackedInline):
    analysis_link = FinalMarkCrewAdmin.analysis_link
    readonly_fields = ("analysis_link",)
    model = FinalMarkCrew
    extra = 1
    max_num = 1

    fieldsets = (
        ("Инструктаж", {
            "fields": ("preflight_brief_with_fa",),
        }),
        ("Работа экипажа", {
            "fields": (
                "free_communication",
                "capt_as_leader",
                "general_mark_capt",
                "general_mark_copilot",
                "total_general_mark",
            ),
        }),
        ("Общее впечатление", {
            "fields": ("general_notes", "analysis_link"),
        }),
    )

class DescentApproachInline(admin.StackedInline):
    model = DescentApproach
    extra = 0
    max_num = 1
    show_change_link = True

    fieldsets = (
        (
            "Подготовка и снижение",
            {
                "fields": (
                    "ten_thousand_brief",
                    "start_of_descent",
                    "descent_trajectory",
                    "describe_deviation",
                ),
            },
        ),
        (
            "Заход на посадку",
            {
                "fields": (
                    "approach_mode",
                    "flap_settings",
                ),
            },
        ),
    )

@admin.register(DescentApproach)
class DescentApproachAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "audit_sheet",
        "ten_thousand_brief",
        "start_of_descent",
        "descent_trajectory",
        "approach_mode",
        "flap_settings",
    )
    search_fields = ("audit_sheet__audit_number",)
    list_filter = (
        "ten_thousand_brief",
        "start_of_descent",
        "descent_trajectory",
        "approach_mode",
        "flap_settings",
    )
    autocomplete_fields = ("audit_sheet",)
    list_select_related = ("audit_sheet",)


class LandingInline(admin.StackedInline):
    model = Landing
    extra = 0
    max_num = 1
    show_change_link = True
    fields = (
        "threshold_height",
        "flare_and_touch_distance",
        "g_load",
    )


class RolloutAndTaxingAndParkingInline(admin.StackedInline):
    model = RolloutAndTaxingAndParking
    extra = 0
    max_num = 1
    show_change_link = True
    fields = (
        "thrust_reverser_on",
        "thrust_reverser_off",
        "taxi_speed",
        "taxi_speed_turn",
        "parking",
    )

@admin.register(AuditSheet)
class AuditSheetAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "audit_number",
        "date",
        "leg_number",
        "auditor",
        "aircraft",
        "departure",
        "arrival",
        "pilot_flying",
        "is_delay",
        "delay",
    )
    search_fields = (
        "audit_number",
        "auditor__name",
        "departure__airport_code",
        "arrival__airport_code",
    )
    list_filter = (
        "aircraft",
        "auditor",
        "departure",
        "arrival",
        "pilot_flying",
        "is_delay",
    )
    autocomplete_fields = (
        "auditor",
        "aircraft",
        "captain",
        "first_officer",
        "second_officer",
        "flight_engineer",
        "departure",
        "arrival",
    )
    list_select_related = ("auditor", "aircraft", "departure", "arrival")
    date_hierarchy = "date"
    inlines = (
        AuditMistakeInline,
        AuditThreatInline,
        AuditCriterionRatingInline,
        TypeApproachAndWeatherInline,
        StabilizedApproachAssessmentInline,
        AuditAssessmentInline,
        AuditSafetyConditionInline,
        FinalMarkCrewInline,
        DescentApproachInline,
        LandingInline,
        RolloutAndTaxingAndParkingInline,
    )
    fieldsets = (
        (
            "Проверка",
            {"fields": ("audit_number", "date", "leg_number", "auditor", "aircraft")},
        ),
        (
            "Экипаж",
            {
                "fields": (
                    "captain",
                    "first_officer",
                    "second_officer",
                    "flight_engineer",
                    "working_together",
                    "pilot_flying",
                )
            },
        ),
        (
            "Маршрут и задержка",
            {"fields": ("departure", "arrival", "is_delay", "delay")},
        ),
    )


@admin.register(AuditSafetyCondition)
class AuditSafetyConditionAdmin(admin.ModelAdmin):
    form = AuditSafetyConditionForm

    list_display = (
        "id",
        "audit_sheet",
        "condition",
        "flight_phase",
        "observed_at",
        "result",
    )
    search_fields = (
        "audit_sheet__audit_number",
        "condition__name",
        "comment",
    )
    list_filter = ("flight_phase", "condition__section", "result")
    autocomplete_fields = (
        "audit_sheet",
        "condition",
        "flight_phase",
        "mistakes",
    )
    list_select_related = ("audit_sheet", "condition", "flight_phase")
    date_hierarchy = "observed_at"

class SafetyConditionExcelImportForm(forms.Form):
    file = forms.FileField(
        label="Excel-файл",
        help_text="Формат .xlsx. Колонки: code, section, name.",
    )
    sheet = forms.CharField(
        label="Название листа",
        required=False,
        help_text="Оставь пустым для активного листа.",
    )
    dry_run = forms.BooleanField(
        label="Только проверить, без сохранения",
        required=False,
        initial=True,
    )

    def clean_file(self):
        uploaded = self.cleaned_data["file"]

        if Path(uploaded.name).suffix.lower() != ".xlsx":
            raise forms.ValidationError("Выбери файл в формате .xlsx.")

        return uploaded


@admin.register(AuditCriterionRating)
class AuditCriterionRatingAdmin(admin.ModelAdmin):
    list_display = ("audit_sheet", "stage", "criterion", "score")
    search_fields = (
        "audit_sheet__audit_number",
        "criterion__code",
        "criterion__name",
        "comment",
    )
    list_filter = ("stage", "score", "criterion__section")
    autocomplete_fields = ("audit_sheet", "stage", "criterion")
    list_select_related = ("audit_sheet", "stage", "criterion__section")


@admin.register(AuditMistake)
class AuditMistakeAdmin(admin.ModelAdmin):
    list_display = ("id", "audit_sheet", "mistake", "observed_at", "flight_phase")
    search_fields = (
        "audit_sheet__audit_number",
        "mistake__code",
        "mistake__name",
        "comment",
    )
    list_filter = ("flight_phase", "mistake")
    autocomplete_fields = ("audit_sheet", "mistake", "flight_phase")
    list_select_related = ("audit_sheet", "mistake", "flight_phase")
    date_hierarchy = "observed_at"


@admin.register(AuditThreat)
class AuditThreatAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "audit_sheet",
        "threat",
        "observed_at",
        "flight_phase",
        "was_control_effective",
        "correct_actions",
    )

    search_fields = (
        "audit_sheet__audit_number",
        "threat__code",
        "threat__describe",
        "comment",
    )
    list_filter = (
        "flight_phase",
        "threat",
        "was_control_effective",
        "correct_actions",
    )
    autocomplete_fields = ("audit_sheet", "threat", "flight_phase")
    list_select_related = ("audit_sheet", "threat", "flight_phase")
    date_hierarchy = "observed_at"


@admin.register(AssessmentStage)
class AssessmentStageAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "template", "sort_order")
    search_fields = ("code", "name", "template__name", "template__version")
    autocomplete_fields = ("template",)
    list_select_related = ("template",)
    fields = ("code", "name", "sort_order", "template")


@admin.register(AssessmentCriterion)
class AssessmentCriterionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "section")
    search_fields = ("code", "name", "section__name")
    list_filter = ("section",)
    list_select_related = ("section",)


@admin.register(StabilizedApproachAssessment)
class StabilizedApproachAssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "audit_sheet",
        "stage",
        "speed_deviation",
        "rate_of_descent_deviation",
        "thrust_settings",
        "landing_config",
    )
    search_fields = ("audit_sheet__audit_number", "comment")
    list_filter = (
        "stage",
        "rate_of_descent_deviation",
        "thrust_settings",
        "landing_config",
    )
    autocomplete_fields = ("audit_sheet",)
    list_select_related = ("audit_sheet",)
@admin.register(Landing)
class LandingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "audit_sheet",
        "threshold_height",
        "flare_and_touch_distance",
        "g_load",
    )
    search_fields = ("audit_sheet__audit_number",)
    list_filter = (
        "threshold_height",
        "flare_and_touch_distance",
        "g_load",
    )
    autocomplete_fields = ("audit_sheet",)
    list_select_related = ("audit_sheet",)


@admin.register(RolloutAndTaxingAndParking)
class RolloutAndTaxingAndParkingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "audit_sheet",
        "thrust_reverser_on",
        "thrust_reverser_off",
        "taxi_speed",
        "taxi_speed_turn",
        "parking",
    )
    search_fields = ("audit_sheet__audit_number",)
    list_filter = (
        "thrust_reverser_on",
        "thrust_reverser_off",
        "taxi_speed",
        "taxi_speed_turn",
        "parking",
    )
    autocomplete_fields = ("audit_sheet",)
    list_select_related = ("audit_sheet",)

from django.utils.html import format_html
