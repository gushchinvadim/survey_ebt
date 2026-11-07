from functools import wraps
from zoneinfo import ZoneInfo

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone

from .models import PortalProfile

COORDINATOR_GROUP = "LOSA Координаторы"
AUDITOR_GROUP = "LOSA Аудиторы"


def profile_for(user):
    return PortalProfile.objects.filter(user=user).select_related("auditor").first()


def roles_for(user):
    if not user.is_authenticated or not user.is_active:
        return []
    groups = set(user.groups.values_list("name", flat=True))
    roles = []
    if user.is_superuser or COORDINATOR_GROUP in groups:
        roles.append("coordinator")
    profile = profile_for(user)
    if AUDITOR_GROUP in groups and profile and profile.auditor_id:
        roles.append("auditor")
    return roles


def program_today():
    return timezone.localdate(
        timezone=ZoneInfo(getattr(settings, "LOSA_TIME_ZONE", "Europe/Moscow"))
    )


def user_payload(user):
    profile = profile_for(user)
    return {
        "id": user.pk,
        "username": user.get_username(),
        "name": user.get_full_name().strip()
        or (
            profile.auditor.name
            if profile and profile.auditor_id
            else user.get_username()
        ),
        "roles": roles_for(user),
        "auditor_id": profile.auditor_id if profile else None,
    }


def can_start(assignment, user):
    if assignment.archived_at:
        return False
    profile = profile_for(user)
    return bool(
        "auditor" in roles_for(user)
        and profile
        and profile.auditor_id == assignment.auditor_id
        and assignment.date <= program_today()
        and assignment.status == "scheduled"
    )



def can_view(assignment, user):
    if assignment.archived_at:
        return False
    if can_start(assignment, user):
        return True
    profile = profile_for(user)
    return bool(
        "auditor" in roles_for(user)
        and profile
        and profile.auditor_id == assignment.auditor_id
        and assignment.status == "completed"
        and assignment.audit_sheet_id
        and assignment.date <= program_today()
    )


def visible_assignments(user):
    from .models import AuditAssignment

    queryset = AuditAssignment.objects.filter(archived_at__isnull=True).select_related("flight", "auditor")
    roles = roles_for(user)
    if "coordinator" in roles:
        return queryset
    profile = profile_for(user)
    if "auditor" in roles and profile:
        return queryset.filter(auditor_id=profile.auditor_id)
    return queryset.none()


def portal_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_active:
            return JsonResponse({"detail": "Войдите в систему."}, status=401)
        if not roles_for(request.user):
            return JsonResponse(
                {"detail": "Роль LOSA не назначена. Обратитесь к администратору."},
                status=403,
            )
        return view(request, *args, **kwargs)

    return wrapper
