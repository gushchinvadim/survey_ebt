"""Revision and stale-form protection for audit changes made through Admin."""
from copy import deepcopy
from django import forms
from django.contrib.admin.utils import flatten_fieldsets
from django.db import transaction
from django.db.models import F
from .models import AuditSheet


class RevisionFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = self.instance
        sheet_id = instance.pk if isinstance(instance, AuditSheet) else getattr(instance, 'audit_sheet_id', None)
        revision = AuditSheet.objects.filter(pk=sheet_id).values_list('demography_revision', flat=True).first()
        self.initial['source_revision'] = revision

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk:
            sheet_id = self.instance.pk if isinstance(self.instance, AuditSheet) else getattr(self.instance, 'audit_sheet_id', None)
            current = AuditSheet.objects.filter(pk=sheet_id).values_list('demography_revision', flat=True).first()
            if current is not None and cleaned.get('source_revision') != current:
                raise forms.ValidationError(
                    'Лист изменился после открытия формы. Ваши данные не сохранены. '
                    'Откройте свежую форму в другой вкладке и сравните изменения.'
                )
        return cleaned


class AuditRevisionMixin:
    def get_form(self, request, obj=None, **kwargs):
        base = kwargs.pop('form', self.form)
        form = type('AuditRevisionForm', (RevisionFormMixin, base), {
            'source_revision': forms.IntegerField(required=False, widget=forms.HiddenInput),
        })
        return super().get_form(request, obj, form=form, **kwargs)

    def get_fieldsets(self, request, obj=None):
        fieldsets = deepcopy(super().get_fieldsets(request, obj))
        if 'source_revision' not in flatten_fieldsets(fieldsets):
            name, options = fieldsets[0]
            options['fields'] = tuple(options['fields']) + ('source_revision',)
        return fieldsets

    def _sheet_ids(self, queryset):
        field = 'pk' if self.model is AuditSheet else 'audit_sheet_id'
        return set(queryset.values_list(field, flat=True)) - {None}

    def _lock(self, ids):
        # Same lock order as the mobile API: assignment, then audit sheet.
        from losa_portal.models import AuditAssignment
        list(AuditAssignment.objects.filter(audit_sheet_id__in=ids)
             .order_by('pk').select_for_update().values_list('pk', flat=True))
        list(AuditSheet.objects.filter(pk__in=ids)
             .order_by('pk').select_for_update().values_list('pk', flat=True))

    def _bump(self, ids):
        AuditSheet.objects.filter(pk__in=ids).update(demography_revision=F('demography_revision') + 1)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        if request.method != 'POST':
            return super().changeform_view(request, object_id, form_url, extra_context)
        with transaction.atomic():
            ids = self._sheet_ids(self.get_queryset(request).filter(pk=object_id)) if object_id else set()
            if self.model is not AuditSheet:
                selected = request.POST.get('audit_sheet')
                if selected and selected.isdecimal():
                    ids.add(int(selected))
            self._lock(ids)
            request._audit_revision_ids = ids
            return super().changeform_view(request, object_id, form_url, extra_context)

    def save_related(self, request, form, formsets, change):
        changed = not change or bool(set(form.changed_data) - {'source_revision'}) or any(fs.has_changed() for fs in formsets)
        super().save_related(request, form, formsets, change)
        if changed:
            ids = set(getattr(request, '_audit_revision_ids', set()))
            ids.add(form.instance.pk if self.model is AuditSheet else form.instance.audit_sheet_id)
            self._bump(ids - {None})

    def delete_view(self, request, object_id, extra_context=None):
        if request.method != 'POST':
            return super().delete_view(request, object_id, extra_context)
        with transaction.atomic():
            ids = self._sheet_ids(self.get_queryset(request).filter(pk=object_id))
            self._lock(ids)
            return super().delete_view(request, object_id, extra_context)

    def delete_model(self, request, obj):
        ids = {obj.pk if self.model is AuditSheet else obj.audit_sheet_id}
        super().delete_model(request, obj)
        self._bump(ids - {None})

    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            ids = self._sheet_ids(queryset)
            self._lock(ids)
            super().delete_queryset(request, queryset)
            self._bump(ids)
