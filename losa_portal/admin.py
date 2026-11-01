from django.contrib import admin
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


@admin.register(AuditAssignment)
class AuditAssignmentAdmin(admin.ModelAdmin):
    list_display = ("audit_number", "date", "flight", "auditor", "status")
    list_filter = ("date", "status", "auditor")
    search_fields = ("flight__number", "auditor__name")
    raw_id_fields = ("flight", "captain", "first_officer", "auditor")
    readonly_fields = ("number", "created_by", "created_at", "audit_sheet", "opened_at")
    list_select_related = ("flight__departure", "flight__arrival", "auditor")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
