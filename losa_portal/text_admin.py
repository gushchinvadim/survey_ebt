from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from .models import ObservationTopic, TextObservation
from .text_analysis import permitted, extract_view, review_view


class CoordinatorAdmin(admin.ModelAdmin):
    def has_module_permission(self, request): return permitted(request.user)
    def has_view_permission(self, request, obj=None): return permitted(request.user)
    def has_change_permission(self, request, obj=None): return permitted(request.user)
    def has_add_permission(self, request): return permitted(request.user)
    def has_delete_permission(self, request, obj=None): return False


@admin.register(ObservationTopic)
class ObservationTopicAdmin(CoordinatorAdmin):
    list_display = ('name', 'parent')
    search_fields = ('name',)


@admin.register(TextObservation)
class TextObservationAdmin(CoordinatorAdmin):
    change_list_template = 'admin/losa_portal/text_observation_list.html'
    list_display = ('audit_sheet', 'source_label', 'short_quote', 'nature', 'evidence', 'status', 'source_warning')
    list_filter = ('topics', 'nature', 'evidence', 'status', 'assessment__stage', 'audit_sheet__date')
    search_fields = ('quote', 'note', 'audit_sheet__audit_number')
    filter_horizontal = ('topics',)
    readonly_fields = ('audit_sheet', 'source_link', 'quote', 'source_snapshot', 'source_warning',
                       'created_by', 'updated_by', 'created_at', 'updated_at')
    fields = ('audit_sheet', 'source_link', 'source_warning', 'quote', 'topics', 'nature', 'evidence',
              'note', 'status', 'source_snapshot', 'created_by', 'created_at', 'updated_by', 'updated_at')
    list_select_related = ('audit_sheet', 'assessment__stage', 'final_mark')
    def has_add_permission(self, request): return False
    def get_urls(self):
        return [path('from-stage/<int:pk>/', self.admin_site.admin_view(
                    lambda request, pk: extract_view(request, 'stage', pk)), name='text-analysis-stage'),
                path('from-final/<int:pk>/', self.admin_site.admin_view(
                    lambda request, pk: extract_view(request, 'final', pk)), name='text-analysis-final'),
                path('themes/', self.admin_site.admin_view(review_view), name='text-analysis-review')] + super().get_urls()
    @admin.display(description='Цитата')
    def short_quote(self, obj): return obj.quote[:110]
    @admin.display(description='Состояние источника')
    def source_warning(self, obj):
        return 'Источник изменён — требуется сверка' if obj.source_changed else 'Совпадает со снимком'
    @admin.display(description='Исходный текст')
    def source_link(self, obj):
        if obj.assessment_id:
            url = reverse('admin:losa_auditassessment_change', args=[obj.assessment_id])
        else:
            url = reverse('admin:losa_finalmarkcrew_change', args=[obj.final_mark_id])
        return format_html('<a href="{}">{}</a>', url, obj.source_label)
    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
