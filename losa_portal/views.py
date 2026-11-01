import json

from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .access import (
    AUDITOR_GROUP,
    can_start,
    can_view,
    portal_required,
    roles_for,
    user_payload,
    visible_assignments,
)
from .serializers import AssignmentSerializer
from losa.models import Auditor, Pilot


def read_json(request):
    try:
        value = json.loads(request.body)
        return value if isinstance(value, dict) else None
    except (ValueError, UnicodeDecodeError):
        return None


@never_cache
@require_GET
@ensure_csrf_cookie
def csrf_view(request):
    return JsonResponse({"detail": "CSRF cookie установлена."})


@never_cache
@require_POST
@csrf_protect
def login_view(request):
    data = read_json(request)
    if data is None:
        return JsonResponse({"detail": "Ожидается JSON-объект."}, status=400)
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return JsonResponse({"detail": "Укажите логин и пароль."}, status=400)
    user = authenticate(request, username=username.strip(), password=password)
    if user is None:
        return JsonResponse({"detail": "Неверный логин или пароль."}, status=401)
    if not roles_for(user):
        return JsonResponse(
            {"detail": "Учётная запись не имеет настроенной роли LOSA."}, status=403
        )
    login(request, user)
    return JsonResponse(user_payload(user))


@never_cache
@require_GET
def me_view(request):
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({"detail": "Сессия не найдена."}, status=401)
    return JsonResponse(user_payload(request.user))


@never_cache
@require_POST
@csrf_protect
def logout_view(request):
    logout(request)
    return JsonResponse({"detail": "Вы вышли из системы."})


@never_cache
@require_GET
@portal_required
def catalog_view(request):
    from .models import Flight

    assignments = visible_assignments(request.user)
    coordinator = "coordinator" in roles_for(request.user)
    flights = Flight.objects.select_related("departure", "arrival", "aircraft")
    pilots = Pilot.objects.select_related("company")
    auditors = Auditor.objects.all()
    if not coordinator:
        flights = flights.filter(pk__in=assignments.values("flight_id"))
        pilot_ids = set(assignments.values_list("captain_id", flat=True)) | set(
            assignments.values_list("first_officer_id", flat=True)
        )
        pilots = pilots.filter(pk__in=pilot_ids)
        auditors = auditors.filter(pk__in=assignments.values("auditor_id"))
    # Include inactive flights referenced by historical assignments.
    eligible_auditors = set(
        Auditor.objects.filter(
            portal_profile__user__is_active=True,
            portal_profile__user__groups__name=AUDITOR_GROUP,
        ).values_list("pk", flat=True)
    )
    return JsonResponse(
        {
            "flights": [
                {
                    "id": f.pk,
                    "number": f.number,
                    "departure": f.departure.airport_code,
                    "arrival": f.arrival.airport_code,
                    "time": f.time.strftime("%H:%M"),
                    "aircraft": f.aircraft.aircraft_type,
                    "is_active": f.is_active,
                }
                for f in flights
            ],
            "pilots": [
                {
                    "id": p.pk,
                    "label": f"{p.company.company_code} / {p.pilot_id} · {p.get_position_display()}",
                }
                for p in pilots
            ],
            "auditors": [
                {"id": a.pk, "name": a.name, "is_active": a.pk in eligible_auditors}
                for a in auditors
            ],
        }
    )


@never_cache
@require_http_methods(["GET", "POST"])
@csrf_protect
@portal_required
def assignments_view(request):
    if request.method == "GET":
        return JsonResponse(
            AssignmentSerializer(
                visible_assignments(request.user),
                many=True,
                context={"request": request},
            ).data,
            safe=False,
        )

    if "coordinator" not in roles_for(request.user):
        return JsonResponse({"detail": "Назначения создаёт координатор."}, status=403)
    data = read_json(request)
    if data is None:
        return JsonResponse({"detail": "Ожидается JSON-объект."}, status=400)
    serializer = AssignmentSerializer(data=data, context={"request": request})
    if not serializer.is_valid():
        return JsonResponse(
            {"detail": "Проверьте данные назначения.", "errors": serializer.errors},
            status=400,
        )
    try:
        with transaction.atomic():
            serializer.save(created_by=request.user)
    except IntegrityError:
        return JsonResponse(
            {
                "detail": "Назначение конфликтует с существующими данными. Обновите расписание."
            },
            status=409,
        )
    return JsonResponse(serializer.data, status=201)


@never_cache
@require_GET
@portal_required
def assignment_entry_view(request, pk):
    assignment = get_object_or_404(visible_assignments(request.user), pk=pk)
    if not can_view(assignment, request.user):
        return JsonResponse(
            {
                "detail": "Проверка доступна назначенному аудитору с назначенной даты."
            },
            status=403,
        )
    return JsonResponse(
        AssignmentSerializer(assignment, context={"request": request}).data
    )
