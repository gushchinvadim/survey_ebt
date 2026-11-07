"""Coordinator-only archival. Source data and published reports remain in the DB."""
import hashlib
import json
from copy import copy
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from losa.models import AuditSheet, AuditThreat, AuditMistake
from .models import AuditAssignment, RoundTableCycle
from .analytics import coordinator_required
from .views import read_json


def archive_basis(cycle, state, events=None):
    from .reports import event_summary
    from .round_table import source_data, source_text, key_for
    assignments = list(cycle.assignments.order_by('pk').values(
        'id', 'status', 'date', 'flight_id', 'captain_id', 'first_officer_id', 'auditor_id', 'audit_sheet_id', 'audit_sheet__demography_revision'))
    reviews = list(cycle.reviews.order_by('pk').values(
        'id', 'assessment_id', 'final_mark_id', 'revision', 'source_snapshot', 'agreed_text', 'decision', 'note', 'updated_at'))
    observations = []
    for review in cycle.reviews.order_by('pk'):
        for item in review.observations.order_by('pk').prefetch_related('topics'):
            observations.append({'id': item.pk, 'quote': item.quote, 'nature': item.nature,
                'evidence': item.evidence, 'note': item.note, 'status': item.status,
                'source_snapshot': item.source_snapshot,
                'topics': list(item.topics.order_by('pk').values('id', 'name', 'parent_id'))})
    sheets = [row['audit_sheet_id'] for row in assignments]
    if events is None:
        events = {'threats': event_summary(AuditThreat.objects.filter(audit_sheet_id__in=sheets), 'threat'),
                  'errors': event_summary(AuditMistake.objects.filter(audit_sheet_id__in=sheets), 'mistake')}
    sources = [{'key': key_for(source), 'digest': hashlib.sha256(source_text(source).encode()).hexdigest()}
               for source in source_data(cycle)]
    value = {'cycle_name': cycle.name, 'source_fingerprints': sorted(sources, key=lambda row: row['key']), 'cycle_revision': cycle.revision, 'assignments': assignments, 'reviews': reviews,
        'observations': sorted(observations, key=lambda row: row['id']),
        'sources': sorted(state['sources'], key=lambda row: row['key']),
        'summary': sorted(state['summary'], key=lambda row: row['id']),
        'cases': sorted(state['cases'], key=lambda row: row['id']),
        'sheets': state['sheets'], 'texts': state['total'], 'events': events}
    digest = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
    return {'format': 1, 'digest': digest, 'assignment_ids': [str(row['id']) for row in assignments]}


def locked_members(cycle):
    rows = list(AuditAssignment.objects.filter(pk__in=cycle.assignments.values('pk')).order_by('pk').select_for_update())
    list(AuditSheet.objects.filter(pk__in=[row.audit_sheet_id for row in rows if row.audit_sheet_id])
         .order_by('pk').select_for_update().values_list('pk', flat=True))
    return rows


def preview(request, cycle, rows):
    from .round_table import cycle_view
    cloned = copy(request); cloned.method = 'GET'
    state = json.loads(cycle_view(cloned, cycle.pk).content)
    report = cycle.reports.first()
    archived = sum(row.archived_at is not None for row in rows)
    already = bool(rows) and archived == len(rows)
    reasons = []
    if not rows: reasons.append('В цикле нет проверок.')
    if not cycle.closed: reasons.append('Сначала завершите обсуждение цикла.')
    if not state['ready'] or state['stale_count']: reasons.append('Не все проверки и согласованные наблюдения готовы.')
    if any(row['source_changed'] for row in state['sources']):
        reasons.append('Исходные тексты изменились после анализа. Пересогласуйте их и выпустите актуальный отчет.')
    if any(row.status != 'completed' or not row.audit_sheet_id for row in rows):
        reasons.append('Все проверки должны быть завершены и иметь сохраненные листы.')
    if any(row.review_cycles.filter(closed=False).exists() for row in rows):
        reasons.append('Некоторые проверки также входят в открытые циклы. Сначала завершите их обсуждение.')
    basis = archive_basis(cycle, state)
    if not report:
        reasons.append('Сначала сформируйте отчет и решения PDF.')
    elif report.payload.get('_archive_basis', {}).get('format') != 1:
        reasons.append('Для прежнего отчета нет контрольного снимка. Выпустите новую версию отчета перед архивированием.')
    elif report.payload['_archive_basis'] != basis:
        reasons.append('Состав или данные цикла изменились после выпуска отчета. Выпустите актуальную версию отчета.')
    return {'cycle_id': cycle.pk, 'revision': cycle.revision, 'closed': cycle.closed,
        'report_id': report.pk if report else None, 'report_version': report.version if report else None,
        'digest': basis['digest'], 'ready': not reasons and not already, 'reasons': [] if already else reasons,
        'already_archived': already, 'archived_count': archived,
        'assignments': [{'id': str(row.pk), 'number': row.audit_number, 'archived': row.archived_at is not None} for row in rows]}


@never_cache
@require_http_methods(['GET', 'POST'])
@csrf_protect
@coordinator_required
def archive_cycle_view(request, pk):
    with transaction.atomic():
        cycle = get_object_or_404(RoundTableCycle.objects.select_for_update(), pk=pk)
        rows = locked_members(cycle)
        state = preview(request, cycle, rows)
        if request.method == 'GET': return JsonResponse(state)
        data = read_json(request)
        if not isinstance(data, dict) or set(data) != {'revision', 'report_id', 'digest'} or type(data['revision']) is not int or type(data['report_id']) is not int:
            return JsonResponse({'detail': 'Проверьте запрос архивирования.'}, status=400)
        if state['already_archived']:
            return JsonResponse({**state, 'newly_archived': 0})
        if not state['ready']:
            return JsonResponse({'detail': 'Архивирование недоступно.', 'reasons': state['reasons']}, status=409)
        if any(data[key] != state[key] for key in ('revision', 'report_id', 'digest')):
            return JsonResponse({'detail': 'Предварительный просмотр устарел. Проверьте архивирование заново.'}, status=409)
        targets = [row for row in rows if row.archived_at is None]
        now = timezone.now()
        AuditAssignment.objects.filter(pk__in=[row.pk for row in targets]).update(
            archived_at=now, archived_by=request.user, archived_cycle=cycle, archived_report_id=state['report_id'])
        content_type = ContentType.objects.get_for_model(AuditAssignment)
        LogEntry.objects.bulk_create([LogEntry(user_id=request.user.pk, content_type_id=content_type.pk,
            object_id=str(row.pk), object_repr=row.audit_number, action_flag=CHANGE,
            change_message=f'Архивировано по циклу {cycle.pk}, отчет {state["report_id"]}.') for row in targets])
        return JsonResponse({**state, 'ready': False, 'already_archived': True,
                             'archived_count': len(rows), 'newly_archived': len(targets),
                             'assignments': [{**item, 'archived': True} for item in state['assignments']]})
