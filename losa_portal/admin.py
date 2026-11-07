from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from .access import roles_for
from .models import AuditAssignment, Flight, PortalProfile


@admin.register(PortalProfile)
class PortalProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "auditor")
    search_fields = ("user__username", "auditor__name")
    raw_id_fields = ("user", "auditor")
    list_select_related = ("user", "auditor")


@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = ("number", "departure", "arrival", "time", "aircraft", "is_active")
    search_fields = ("number",)
    list_filter = ("is_active", "aircraft")
    raw_id_fields = ("departure", "arrival", "aircraft")
    list_select_related = ("departure", "arrival", "aircraft")


class ArchiveStateFilter(admin.SimpleListFilter):
    title = "Архив"
    parameter_name = "archive_state"

    def lookups(self, request, model_admin):
        return (("active", "Текущие"), ("archived", "Архив"), ("all", "Все"))

    def queryset(self, request, queryset):
        if self.value() == "archived":
            return queryset.filter(archived_at__isnull=False)
        if self.value() == "all":
            return queryset
        return queryset.filter(archived_at__isnull=True)


@admin.register(AuditAssignment)
class AuditAssignmentAdmin(admin.ModelAdmin):
    list_display = ("audit_number", "date", "flight", "auditor", "status", "archived_at", "archived_cycle")
    list_filter = (ArchiveStateFilter, "date", "status", "auditor", "archived_cycle")
    search_fields = ("flight__number", "auditor__name")
    raw_id_fields = ("flight", "captain", "first_officer", "auditor")
    readonly_fields = ("number", "created_by", "created_at", "audit_sheet", "opened_at", "archived_at", "archived_by", "archived_cycle", "archived_report")
    list_select_related = ("flight__departure", "flight__arrival", "auditor")

    actions = ("restore_from_archive",)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj and obj.archived_at:
            return tuple(fields) + tuple(field.name for field in self.model._meta.fields if field.name not in fields)
        return fields

    def has_delete_permission(self, request, obj=None):
        if obj and obj.archived_at:
            return False
        return super().has_delete_permission(request, obj)

    def delete_queryset(self, request, queryset):
        if queryset.filter(archived_at__isnull=False).exists():
            raise PermissionDenied("Архивные назначения нельзя удалить. Сначала верните их из архива.")
        return super().delete_queryset(request, queryset)

    @admin.action(description="Вернуть выбранные проверки из архива")
    def restore_from_archive(self, request, queryset):
        if "coordinator" not in roles_for(request.user):
            raise PermissionDenied("Возвращает из архива только координатор.")
        with transaction.atomic():
            rows = list(queryset.filter(archived_at__isnull=False).order_by("pk").select_for_update())
            for row in rows:
                message = f"Возвращено из архива. Цикл {row.archived_cycle_id}, отчет {row.archived_report_id}."
                row.archived_at = row.archived_by = row.archived_cycle = row.archived_report = None
                row.save(update_fields=["archived_at", "archived_by", "archived_cycle", "archived_report"])
                self.log_change(request, row, message)
        self.message_user(request, f"Возвращено из архива: {len(rows)}. Статус остается «Завершена»; аудитор может вернуть лист в работу через браузер.", messages.SUCCESS)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

# Separate module keeps text analysis independent of scheduling and data capture.
from . import text_admin  # noqa: F401,E402
