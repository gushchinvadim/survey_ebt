"""Coordinator portal: explicit cycle membership, decisions and approved text excerpts."""
from collections import defaultdict
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from rest_framework import serializers
from losa.models import AuditAssessment, FinalMarkCrew, AuditCriterionRating, AuditThreat, AuditMistake
from .models import AuditAssignment, RoundTableCycle, SourceReview, ObservationTopic, TextObservation
from .analytics import coordinator_required
from .views import read_json
from .text_analysis import digest


class CycleInput(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    assignments = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=1000)


class DecisionInput(serializers.Serializer):
    decision = serializers.ChoiceField(choices=SourceReview.DECISIONS)
    agreed_text = serializers.CharField(allow_blank=True, trim_whitespace=False, max_length=100000)
    note = serializers.CharField(allow_blank=True, max_length=10000)
    revision = serializers.IntegerField(min_value=0)
    source_digest = serializers.CharField(max_length=64)


class ObservationInput(serializers.Serializer):
    quote = serializers.CharField(trim_whitespace=False, max_length=100000)
    topics = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=30)
    nature = serializers.ChoiceField(choices=TextObservation.NATURES)
    evidence = serializers.ChoiceField(choices=TextObservation.EVIDENCE)
    note = serializers.CharField(allow_blank=True, max_length=10000)
    revision = serializers.IntegerField(min_value=1)


def parsed(request, klass):
    s = klass(data=read_json(request))
    return s.validated_data if s.is_valid() else None


def failure(message, status=400): return JsonResponse({'detail': message}, status=status)


def assignment_row(a):
    s = a.audit_sheet
    return {'id': str(a.pk), 'sheet_id': s.pk, 'number': s.audit_number, 'date': str(s.date),
            'aircraft': s.aircraft.aircraft_type, 'route': f'{s.actual_departure or s.departure.airport_code} → {s.actual_arrival or s.arrival.airport_code}'}


def eligible():
    return AuditAssignment.objects.filter(status='completed', audit_sheet__isnull=False, archived_at__isnull=True).select_related(
        'audit_sheet__aircraft', 'audit_sheet__departure', 'audit_sheet__arrival')


def cycle_row(c):
    return {'id': c.pk, 'name': c.name, 'closed': c.closed, 'revision': c.revision,
            'count': c.assignments.count(), 'archived_count': c.assignments.filter(archived_at__isnull=False).count()}


@never_cache
@require_http_methods(['GET', 'POST'])
@csrf_protect
@coordinator_required
def cycles_view(request):
    if request.method == 'GET':
        return JsonResponse({'cycles': [cycle_row(c) for c in RoundTableCycle.objects.all()],
                             'candidates': [assignment_row(a) for a in eligible().order_by('audit_sheet__date', 'pk')]})
    values = parsed(request, CycleInput)
    if not values: return failure('Укажите название и хотя бы одну завершённую проверку.')
    wanted = set(values['assignments'])
    with transaction.atomic():
        rows = list(eligible().select_for_update().filter(pk__in=wanted))
        if {a.pk for a in rows} != wanted:
            return failure('В цикл можно включить только завершённые проверки с сохранённым листом.')
        c = RoundTableCycle.objects.create(name=values['name'], created_by=request.user)
        c.assignments.set(rows)
    return JsonResponse(cycle_row(c), status=201)


def source_data(cycle):
    sheet_ids = list(cycle.assignments.values_list('audit_sheet_id', flat=True))
    return list(AuditAssessment.objects.filter(audit_sheet_id__in=sheet_ids).select_related('stage', 'audit_sheet')) + list(
        FinalMarkCrew.objects.filter(audit_sheet_id__in=sheet_ids).select_related('audit_sheet'))


def key_for(source): return f"{'stage' if isinstance(source, AuditAssessment) else 'final'}:{source.pk}"


def source_for(cycle, kind, pk, lock=False):
    if kind not in {'stage', 'final'}: raise Http404
    model = AuditAssessment if kind == 'stage' else FinalMarkCrew
    qs = model.objects
    if lock: qs = qs.select_for_update()
    return get_object_or_404(qs, pk=pk, audit_sheet_id__in=cycle.assignments.values('audit_sheet_id'))


def source_text(source): return source.facts if isinstance(source, AuditAssessment) else source.general_notes


def review_for(cycle, source):
    return SourceReview.objects.filter(cycle=cycle, **({'assessment': source} if isinstance(source, AuditAssessment) else {'final_mark': source})).first()


def valid_observation(o, review, frozen=False):
    return (o.status == 'included' and o.source_snapshot == review.agreed_text
            and o.quote in review.agreed_text and (frozen or not review.original_changed))


def observation_row(o, review=None):
    return {'id': o.pk, 'quote': o.quote, 'topics': [t.pk for t in o.topics.all()],
            'nature': o.nature, 'evidence': o.evidence, 'note': o.note, 'status': o.status,
            'stale': bool(review and o.source_snapshot != review.agreed_text)}


@never_cache
@require_http_methods(['GET', 'POST', 'DELETE'])
@csrf_protect
@coordinator_required
def cycle_view(request, pk):
    with transaction.atomic():
        c = get_object_or_404(RoundTableCycle.objects.select_for_update() if request.method in {'POST', 'DELETE'} else RoundTableCycle.objects, pk=pk)
        if request.method == 'DELETE':
            data = read_json(request) or {}
            if (not isinstance(data, dict) or type(data.get('revision')) is not int
                    or data['revision'] != c.revision or data.get('name') != c.name):
                return failure('Подтверждение не совпадает или цикл изменён. Обновите страницу.', 409)
            if c.reports.exists():
                return failure('У цикла есть опубликованные отчеты. Такой цикл нельзя удалить.', 409)
            if c.archived_assignments.exists():
                return failure('По этому циклу проверки отправлены в архив. Удаление недоступно.', 409)
            from django.contrib.admin.models import LogEntry, DELETION
            from django.contrib.contenttypes.models import ContentType
            LogEntry.objects.create(user=request.user,
                content_type=ContentType.objects.get_for_model(c), object_id=str(c.pk),
                object_repr=c.name[:200], action_flag=DELETION,
                change_message='Координатор удалил ошибочный цикл, его решения и разметку. Проверки сохранены.')
            TextObservation.objects.filter(round_table_review__cycle=c).delete()
            c.reviews.all().delete()
            c.delete()
            return JsonResponse({'deleted': True})
        sources = source_data(c)
        reviews = list(c.reviews.select_related('assessment', 'final_mark', 'updated_by'))
        lookup = {f"{'stage' if r.assessment_id else 'final'}:{r.assessment_id or r.final_mark_id}": r for r in reviews}
        rows = []
        for source in sources:
            r = lookup.get(key_for(source)); current = source_text(source)
            resolved = bool(r and r.decision != 'pending' and (c.closed or r.source_snapshot == current))
            rows.append({'key': key_for(source), 'sheet_id': source.audit_sheet_id,
                'number': source.audit_sheet.audit_number, 'stage': str(source.stage) if isinstance(source, AuditAssessment) else 'Общее впечатление',
                'decision': r.decision if r else 'unreviewed', 'resolved': resolved,
                'source_changed': bool(r and r.source_snapshot != current)})
        ready = bool(rows) and all(r['resolved'] for r in rows)
        represented = {r['sheet_id'] for r in rows}
        all_sheets = set(c.assignments.values_list('audit_sheet_id', flat=True))
        ready = ready and all_sheets <= represented and not c.assignments.exclude(status='completed').exists()
        observations = TextObservation.objects.filter(round_table_review__cycle=c).select_related(
            'round_table_review__assessment', 'round_table_review__final_mark', 'audit_sheet', 'assessment__stage').prefetch_related('topics')
        kept = [o for o in observations if o.round_table_review.decision != 'pending' and valid_observation(o, o.round_table_review, c.closed)]
        stale_count = sum(o.status == 'included' and not valid_observation(o, o.round_table_review, c.closed) for o in observations)
        if request.method == 'POST':
            data = read_json(request) or {}
            if type(data.get('revision')) is not int or data['revision'] != c.revision:
                return failure('Цикл изменён другим участником. Обновите страницу.',409)
            if type(data.get('closed')) is not bool: return failure('Укажите состояние цикла.')
            if not data['closed'] and c.assignments.filter(archived_at__isnull=False).exists():
                return failure('Сначала верните проверки из архива в админке координатора.',409)
            if data['closed'] and (not ready or stale_count):
                return failure('Сначала согласуйте все сохранённые тексты, устраните устаревшие карточки и завершите проверки.')
            c.closed = data['closed']; c.revision += 1; c.save(update_fields=['closed','revision'])
            return JsonResponse(cycle_row(c))
        topic_groups = {}
        for o in kept:
            for t in o.topics.all():
                g = topic_groups.setdefault(t.pk, {'id': t.pk,'name':t.name,'sheets':set(),'difficulty':set(),'practice':set(),'neutral':set()})
                g['sheets'].add(o.audit_sheet_id);g[o.nature].add(o.audit_sheet_id)
        denominator = len(all_sheets)
        summary = []
        for g in topic_groups.values():
            summary.append({'id':g['id'],'name':g['name'],'sheets':len(g['sheets']),
                'percent':round(100*len(g['sheets'])/denominator) if denominator else 0,
                'difficulty':len(g['difficulty']),'practice':len(g['practice'])})
        cases = [{**observation_row(o,o.round_table_review),'source_key':f"{'stage' if o.assessment_id else 'final'}:{o.assessment_id or o.final_mark_id}",
                  'number':o.audit_sheet.audit_number,'stage':str(o.assessment.stage) if o.assessment_id else 'Общее впечатление'} for o in kept]
        return JsonResponse({'cycle':cycle_row(c),'sources':rows,'summary':summary,'cases':cases,
            'sheets':denominator,'resolved':sum(r['resolved'] for r in rows),'total':len(rows),
            'ready':ready,'stale_count':stale_count,'sheets_without_texts':len(all_sheets-represented),
            'topics':[{'id':t.pk,'name':t.name,'parent':t.parent_id} for t in ObservationTopic.objects.all()]})


@never_cache
@require_http_methods(['GET', 'PUT'])
@csrf_protect
@coordinator_required
def source_view(request, cycle_pk, kind, pk):
    with transaction.atomic():
        c = get_object_or_404(RoundTableCycle.objects.select_for_update() if request.method == 'PUT' else RoundTableCycle.objects, pk=cycle_pk)
        source = source_for(c,kind,pk,request.method=='PUT')
        r = review_for(c,source); text = source_text(source)
        if request.method == 'PUT':
            if c.closed: return failure('Цикл завершён. Верните его к обсуждению.',409)
            data = parsed(request,DecisionInput)
            if not data: return failure('Проверьте решение, текст и версию записи.')
            if data['revision'] != (r.revision if r else 0) or data['source_digest'] != digest(text):
                return failure('Исходный текст или решение изменились. Обновите страницу перед сохранением.',409)
            if data['decision']=='revised' and (not data['agreed_text'].strip() or data['agreed_text']==text):
                return failure('Для уточнения укажите изменённую согласованную формулировку.')
            agreed = text if data['decision']=='confirmed' else data['agreed_text']
            values = dict(source_snapshot=text,agreed_text=agreed,decision=data['decision'],note=data['note'],updated_by=request.user)
            if r:
                r.history = [*r.history, {'revision':r.revision,'decision':r.decision,
                    'source_snapshot':r.source_snapshot,'agreed_text':r.agreed_text,'note':r.note,
                    'updated_by':r.updated_by.get_username(),'updated_at':r.updated_at.isoformat()}]
                for field,value in values.items(): setattr(r,field,value)
                r.revision+=1;r.save()
            else:
                r=SourceReview.objects.create(cycle=c,assessment=source if kind=='stage' else None,
                    final_mark=source if kind=='final' else None,**values)
            return JsonResponse({'revision':r.revision})
        existing = TextObservation.objects.filter(assessment=source if kind=='stage' else None,
            final_mark=source if kind=='final' else None,round_table_review__isnull=True).prefetch_related('topics')
        cards = r.observations.prefetch_related('topics') if r else []
        scores = []
        if kind=='stage':
            scores=[{'label':x.criterion.name,'score':x.score,'comment':x.comment} for x in AuditCriterionRating.objects.filter(
                audit_sheet_id=source.audit_sheet_id,stage_id=source.stage_id).select_related('criterion')]
        else:
            scores=[{'label':str(source._meta.get_field(f).verbose_name),'score':getattr(source,f),'comment':''} for f in
                ['free_communication','capt_as_leader','general_mark_capt','general_mark_copilot','total_general_mark']]
        events=[]
        for t in AuditThreat.objects.filter(audit_sheet_id=source.audit_sheet_id).select_related('threat','flight_phase'):
            events.append({'kind':'Угроза','label':str(t.threat),'phase':str(t.flight_phase),'comment':t.comment})
        for e in AuditMistake.objects.filter(audit_sheet_id=source.audit_sheet_id).select_related('mistake','flight_phase'):
            events.append({'kind':'Ошибка','label':str(e.mistake),'phase':str(e.flight_phase),'comment':e.comment})
        return JsonResponse({'source':{'key':key_for(source),'number':source.audit_sheet.audit_number,
            'stage':str(source.stage) if kind=='stage' else 'Общее впечатление','text':text,'digest':digest(text)},
            'review':None if not r else {'id':r.pk,'decision':r.decision,'agreed_text':r.agreed_text,'note':r.note,
                'source_snapshot':r.source_snapshot,'revision':r.revision,'changed':r.original_changed,'history':r.history,
                'updated_by':r.updated_by.get_username(),'updated_at':r.updated_at.isoformat()},
            'observations':[observation_row(o,r) for o in cards], 'legacy':[observation_row(o) for o in existing],
            'scores':scores,'events':events,'closed':c.closed})


@never_cache
@require_http_methods(['POST','PATCH'])
@csrf_protect
@coordinator_required
def observation_view(request, cycle_pk, kind, pk):
    with transaction.atomic():
        c = get_object_or_404(RoundTableCycle.objects.select_for_update(), pk=cycle_pk)
        if c.closed:return failure('Цикл завершён. Верните его к обсуждению.',409)
        source=source_for(c,kind,pk,True);r=review_for(c,source)
        if not r or r.decision=='pending' or r.original_changed:
            return failure('Сначала подтвердите или уточните актуальный текст.',409)
        if request.method=='PATCH':
            data=read_json(request) or {}
            if data.get('revision') != r.revision:return failure('Решение изменено. Обновите страницу.',409)
            if type(data.get('id')) is not int or data.get('status') not in dict(TextObservation.STATUSES):return failure('Некорректная карточка.')
            o=get_object_or_404(TextObservation,pk=data['id'],round_table_review=r)
            o.status=data['status'];o.updated_by=request.user;o.save(update_fields=['status','updated_by','updated_at'])
            return JsonResponse({'id':o.pk})
        values=parsed(request,ObservationInput)
        if not values:return failure('Выберите точную цитату, темы, характер и основание.')
        if values['revision']!=r.revision:return failure('Согласованный текст изменён. Обновите страницу.',409)
        topic_ids=set(values['topics'])
        if set(ObservationTopic.objects.filter(pk__in=topic_ids).values_list('pk',flat=True))!=topic_ids:return failure('Одна из тем больше не существует.')
        if not values['quote'].strip() or values['quote'] not in r.agreed_text:return failure('Цитата должна быть точным фрагментом согласованного текста.')
        for o in r.observations.filter(quote=values['quote'],nature=values['nature'],evidence=values['evidence'],status='included').prefetch_related('topics'):
            if {t.pk for t in o.topics.all()}==topic_ids and o.source_snapshot==r.agreed_text:return failure('Такой фрагмент уже включён.')
        o=TextObservation(audit_sheet_id=source.audit_sheet_id,assessment=source if kind=='stage' else None,
            final_mark=source if kind=='final' else None,round_table_review=r,source_snapshot=r.agreed_text,
            quote=values['quote'],nature=values['nature'],evidence=values['evidence'],note=values['note'],
            created_by=request.user,updated_by=request.user)
        o.full_clean();o.save();o.topics.set(topic_ids)
        return JsonResponse({'id':o.pk},status=201)


@never_cache
@require_http_methods(['POST'])
@csrf_protect
@coordinator_required
def topic_view(request):
    data = read_json(request) or {}
    name = data.get('name')
    parent_id = data.get('parent')
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 160:
        return failure('Укажите название темы до 160 символов.')
    if parent_id is not None and (type(parent_id) is not int or not ObservationTopic.objects.filter(pk=parent_id).exists()):
        return failure('Родительская тема не найдена.')
    from django.db import IntegrityError
    try:
        with transaction.atomic():
            t = ObservationTopic(name=name.strip(), parent_id=parent_id)
            t.full_clean();t.save()
    except (ValidationError, IntegrityError):
        return failure('Тема с таким названием уже существует или данные некорректны.')
    return JsonResponse({'id':t.pk,'name':t.name,'parent':t.parent_id}, status=201)
