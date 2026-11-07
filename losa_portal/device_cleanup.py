"""Read-only cleanup eligibility for the current auditor's local device copies."""
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from losa.models import AuditSheet
from .models import AuditAssignment, RoundTableCycle
from .access import portal_required, profile_for, roles_for, can_view


def auditor_id(request):
    profile = profile_for(request.user)
    return profile.auditor_id if 'auditor' in roles_for(request.user) and profile else None


@never_cache
@require_GET
@portal_required
def closed_cycles(request):
    owner = auditor_id(request)
    if not owner:
        return JsonResponse({'detail': 'Очистка доступна только назначенному аудитору.'}, status=403)
    cycles = RoundTableCycle.objects.filter(closed=True, assignments__auditor_id=owner).distinct()
    return JsonResponse({'auditor_id': owner, 'cycles': [
        {'id': cycle.pk, 'name': cycle.name, 'revision': cycle.revision, 'closed': cycle.closed,
         'assignment_count': cycle.assignments.filter(auditor_id=owner).count()}
        for cycle in cycles
    ]})


@never_cache
@require_GET
@portal_required
def manifest(request, pk):
    owner = auditor_id(request)
    if not owner:
        return JsonResponse({'detail': 'Очистка доступна только назначенному аудитору.'}, status=403)
    with transaction.atomic():
        visible_cycles = RoundTableCycle.objects.filter(assignments__auditor_id=owner).values('pk')
        cycle = get_object_or_404(RoundTableCycle.objects.select_for_update().filter(pk__in=visible_cycles), pk=pk)
        if not cycle.closed:
            return JsonResponse({'detail': 'Цикл снова открыт. Очистка недоступна.'}, status=409)
        visible_ids = cycle.assignments.filter(auditor_id=owner).values('pk')
        assignments = list(AuditAssignment.objects.filter(pk__in=visible_ids).order_by('pk').select_for_update())
        sheets = {sheet.pk: sheet for sheet in AuditSheet.objects.filter(
            pk__in=[a.audit_sheet_id for a in assignments if a.audit_sheet_id]
        ).order_by('pk').select_for_update()}
        rows = []
        for assignment in assignments:
            sheet = sheets.get(assignment.audit_sheet_id)
            reason = None
            if assignment.status != 'completed':
                reason = 'Проверка возвращена в работу или еще не завершена.'
            elif not sheet:
                reason = 'На сервере нет сохраненного листа.'
            elif not can_view(assignment, request.user) and not assignment.archived_at:
                reason = 'Сервер не подтверждает доступ к этому листу.'
            elif assignment.review_cycles.filter(closed=False).exists():
                reason = 'Проверка также входит в незавершенный цикл.'
            rows.append({'assignment_id': str(assignment.pk), 'audit_number': assignment.audit_number,
                         'status': assignment.status, 'server_revision': sheet.demography_revision if sheet else None,
                         'eligible': reason is None, 'reason': reason})
        return JsonResponse({'auditor_id': owner,
            'cycle': {'id': cycle.pk, 'name': cycle.name, 'revision': cycle.revision,
                      'closed': cycle.closed, 'assignment_count': len(rows)},
            'assignments': rows})
