"""Human-approved extraction; never modifies auditor source text."""
from hashlib import sha256
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from losa.models import AuditAssessment, FinalMarkCrew, AuditSheet
from .access import roles_for
from .models import ObservationTopic, TextObservation


def permitted(user):
    return user.is_active and user.is_staff and "coordinator" in roles_for(user)


def digest(text):
    return sha256(text.encode()).hexdigest()


class BufferedTopicIterator(forms.models.ModelChoiceIterator):
    """Small topic catalog: render with a regular SELECT, never a named cursor.

    ModelChoiceIterator normally calls QuerySet.iterator(), which uses a
    server-side cursor on PostgreSQL and can fail with transaction pooling.
    Iterating a fresh QuerySet normally buffers results with fetchall().
    """
    def __iter__(self):
        if self.field.empty_label is not None:
            yield ("", self.field.empty_label)
        for obj in self.queryset.all():
            yield self.choice(obj)


class TopicChoiceField(forms.ModelMultipleChoiceField):
    iterator = BufferedTopicIterator


class ExtractForm(forms.Form):
    source_digest = forms.CharField(widget=forms.HiddenInput)
    quote = forms.CharField(label="Точная цитата", strip=False, widget=forms.Textarea(attrs={"rows": 4, "id": "quote-field"}))
    topics = TopicChoiceField(label="Темы / подтемы", queryset=ObservationTopic.objects.all(),
                                            widget=forms.CheckboxSelectMultiple)
    nature = forms.ChoiceField(label="Характер наблюдения", choices=[("", "Выберите характер")] + TextObservation.NATURES)
    evidence = forms.ChoiceField(label="Основание", choices=[("", "Выберите основание")] + TextObservation.EVIDENCE)
    note = forms.CharField(label="Пояснение координатора", required=False, widget=forms.Textarea(attrs={"rows": 3}))


def extract_view(request, kind, pk):
    if not permitted(request.user):
        raise PermissionDenied
    model = AuditAssessment if kind == "stage" else FinalMarkCrew
    source = get_object_or_404(model.objects.select_related("audit_sheet"), pk=pk)
    text = source.facts if kind == "stage" else source.general_notes
    label = str(source.stage) if kind == "stage" else "Общее впечатление"
    form = ExtractForm(request.POST or None, initial={"source_digest": digest(text)})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked = model.objects.select_for_update().get(pk=source.pk)
            current = locked.facts if kind == "stage" else locked.general_notes
            if form.cleaned_data['source_digest'] != digest(current):
                form.add_error(None, "Текст источника изменился. Откройте разбор заново; введённая цитата сохранена в форме.")
            elif not form.cleaned_data['quote'].strip() or form.cleaned_data['quote'] not in current:
                form.add_error('quote', "Выберите или скопируйте точный фрагмент исходного текста без исправлений.")
            else:
                topic_ids = set(form.cleaned_data['topics'].values_list('pk', flat=True))
                duplicates = TextObservation.objects.filter(
                    assessment=source if kind == "stage" else None,
                    final_mark=source if kind == "final" else None,
                    quote=form.cleaned_data['quote'], status='included')
                duplicate = any(set(o.topics.values_list('pk', flat=True)) == topic_ids
                                and o.nature == form.cleaned_data['nature']
                                and o.evidence == form.cleaned_data['evidence'] for o in duplicates)
                if duplicate:
                    form.add_error(None, "Такой фрагмент с этими темами и характером уже включён. Откройте существующую карточку.")
                else:
                    observation = TextObservation(audit_sheet=source.audit_sheet,
                        assessment=source if kind == 'stage' else None,
                        final_mark=source if kind == 'final' else None, source_snapshot=current,
                        quote=form.cleaned_data['quote'], nature=form.cleaned_data['nature'],
                        evidence=form.cleaned_data['evidence'], note=form.cleaned_data['note'],
                        created_by=request.user, updated_by=request.user)
                    observation.full_clean(); observation.save()
                    observation.topics.set(form.cleaned_data['topics'])
                    messages.success(request, "Наблюдение включено в анализ. Можно добавить следующий фрагмент.")
                    return redirect(request.path)
    observations = TextObservation.objects.filter(
        assessment=source if kind == "stage" else None,
        final_mark=source if kind == "final" else None).prefetch_related('topics')
    return TemplateResponse(request, 'admin/losa_portal/text_extract.html', {
        **admin.site.each_context(request), 'title': 'Разобрать для аналитики',
        'source': source, 'source_text': text, 'source_label': label, 'form': form,
        'observations': observations, 'opts': TextObservation._meta,
    })


def review_view(request):
    if not permitted(request.user):
        raise PermissionDenied
    from django.core.paginator import Paginator
    from django.db.models import Q
    qs = TextObservation.objects.filter(status='included').select_related(
        'audit_sheet', 'assessment__stage', 'final_mark').prefetch_related('topics')
    topic = request.GET.get('topic', '')
    nature = request.GET.get('nature', '')
    query = request.GET.get('q', '').strip()
    stage = request.GET.get('stage', '')
    if topic.isdecimal():
        # A parent includes descendants; a leaf stays a concrete subtopic.
        ids = {int(topic)}
        links = list(ObservationTopic.objects.values_list('pk', 'parent_id'))
        while True:
            expanded = ids | {pk for pk, parent in links if parent in ids}
            if expanded == ids: break
            ids = expanded
        qs = qs.filter(topics__pk__in=ids)
    if nature in dict(TextObservation.NATURES): qs = qs.filter(nature=nature)
    if stage == 'final': qs = qs.filter(final_mark__isnull=False)
    elif stage.isdecimal(): qs = qs.filter(assessment__stage_id=int(stage))
    if query: qs = qs.filter(Q(quote__icontains=query) | Q(note__icontains=query) | Q(audit_sheet__audit_number__icontains=query))
    qs = qs.distinct()
    from losa.models import AssessmentStage
    # Denominator is all sheets with approved included observations, not every saved audit.
    total_sheets = TextObservation.objects.filter(status='included').values('audit_sheet_id').distinct().count()
    topic_rows = []
    filtered_sheet_count = qs.values('audit_sheet_id').distinct().count()
    for t in ObservationTopic.objects.all():
        subset = qs.filter(topics=t)
        count = subset.values('audit_sheet_id').distinct().count()
        if count:
            topic_rows.append({'topic': t, 'sheets': count,
                               'difficulties': subset.filter(nature='difficulty').values('audit_sheet_id').distinct().count(),
                               'practices': subset.filter(nature='practice').values('audit_sheet_id').distinct().count(),
                               'percent': round(100 * count / filtered_sheet_count) if filtered_sheet_count else 0})
    return TemplateResponse(request, 'admin/losa_portal/text_review.html', {
        **admin.site.each_context(request), 'title': 'Темы наблюдений',
        'topics': ObservationTopic.objects.all(), 'stages': AssessmentStage.objects.all(),
        'topic': topic, 'nature': nature, 'stage': stage, 'q': query,
        'natures': TextObservation.NATURES, 'topic_rows': topic_rows,
        'total_sheets': total_sheets, 'filtered_sheets': filtered_sheet_count,
        'event_count': qs.count(), 'page_obj': Paginator(qs, 20).get_page(request.GET.get('page')),
        'query_string': request.GET.copy(),
    })
