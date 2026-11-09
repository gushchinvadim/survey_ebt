"""Coordinator creation of planning references; no staff privileges granted."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from rest_framework import serializers
from losa.models import Pilot, Auditor, Airport, Aircraft, Company, Location
from .models import Flight, PortalProfile
from .access import AUDITOR_GROUP, portal_required, roles_for
from .views import read_json

class AirportInput(serializers.ModelSerializer):
    class Meta:
        model = Airport
        fields = ('airport_code', 'airport_name')
    def validate_airport_code(self, value):
        code = value.strip().upper()
        if any(char.isspace() for char in code):
            raise serializers.ValidationError('Код аэропорта не должен содержать пробелы.')
        if Airport.objects.filter(airport_code__iexact=code).exists():
            raise serializers.ValidationError('Аэропорт с таким кодом уже существует. Выберите его в списке.')
        return code

class FlightInput(serializers.ModelSerializer):
    class Meta:
        model = Flight
        fields = ('number', 'departure', 'arrival', 'time', 'aircraft')
    def validate(self, data):
        if data['departure'] == data['arrival']:
            raise serializers.ValidationError('Аэропорты вылета и прилета должны различаться.')
        data['number'] = data['number'].strip().upper()
        if Flight.objects.filter(**data).exists():
            raise serializers.ValidationError('Такой рейс уже есть в справочнике.')
        return data

class PilotInput(serializers.ModelSerializer):
    pilot_id = serializers.IntegerField(min_value=1)
    class Meta:
        model = Pilot
        fields = ('pilot_id', 'company', 'location', 'position', 'experience', 'type_experience', 'fmc_experience')
    def validate(self, data):
        total = data.get('experience')
        if total is not None:
            for key in ('type_experience', 'fmc_experience'):
                if data.get(key) is not None and data[key] > total:
                    raise serializers.ValidationError({key:'Стаж не может превышать общий.'})
        return data

class AuditorInput(serializers.Serializer):
    auditor_code = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=100)
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(trim_whitespace=False, write_only=True, max_length=256)
    def validate(self, data):
        User = get_user_model()
        user = User(username=data['username'])
        try:
            user.full_clean(exclude=['password'])
            validate_password(data['password'], user=user)
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        if User.objects.filter(username__iexact=data['username']).exists():
            raise serializers.ValidationError({'username':'Этот логин уже занят.'})
        if Auditor.objects.filter(auditor_code=data['auditor_code']).exists():
            raise serializers.ValidationError({'auditor_code':'Этот код аудитора уже используется.'})
        return data

def options():
    return {
        'airports':[{'id':x.pk,'label':str(x)} for x in Airport.objects.all()],
        'aircraft':[{'id':x.pk,'label':str(x)} for x in Aircraft.objects.all()],
        'companies':[{'id':x.pk,'label':str(x)} for x in Company.objects.all()],
        'locations':[{'id':x.pk,'label':str(x)} for x in Location.objects.all()],
        'positions':[{'id':k,'label':v} for k,v in Pilot.POSITION_CHOICES],
    }

@never_cache
@require_http_methods(['GET', 'POST'])
@csrf_protect
@portal_required
def references_view(request, kind):
    if 'coordinator' not in roles_for(request.user):
        return JsonResponse({'detail':'Справочники изменяет только координатор.'}, status=403)
    if request.method == 'GET':
        if kind != 'options': return JsonResponse({'detail':'Неизвестный справочник.'},status=404)
        return JsonResponse(options())
    classes = {'airports':AirportInput, 'flights':FlightInput, 'pilots':PilotInput, 'auditors':AuditorInput}
    if kind not in classes: return JsonResponse({'detail':'Неизвестный справочник.'},status=404)
    data=read_json(request)
    if data is None: return JsonResponse({'detail':'Ожидается JSON-объект.'},status=400)
    # Never accept role, is_staff, is_superuser, user IDs or model fields beyond this form.
    form=classes[kind](data=data)
    if set(data)-set(form.fields):
        return JsonResponse({'detail':'Переданы неподдерживаемые поля.'},status=400)
    if not form.is_valid():
        return JsonResponse({'detail':'Проверьте данные справочника.','errors':form.errors},status=400)
    try:
        with transaction.atomic():
            if kind == 'auditors':
                values=form.validated_data
                auditor=Auditor.objects.create(auditor_code=values['auditor_code'], name=values['name'])
                user=get_user_model().objects.create_user(username=values['username'],password=values['password'])
                group,_=Group.objects.get_or_create(name=AUDITOR_GROUP)
                user.groups.add(group)
                PortalProfile.objects.create(user=user,auditor=auditor)
                obj=auditor
            else:
                obj=form.save()
            from django.contrib.admin.models import LogEntry, ADDITION
            from django.contrib.contenttypes.models import ContentType
            LogEntry.objects.create(user=request.user,content_type=ContentType.objects.get_for_model(obj),
                object_id=str(obj.pk),object_repr=str(obj)[:200],action_flag=ADDITION,
                change_message='Создано координатором через интерфейс планирования.')
    except IntegrityError:
        return JsonResponse({'detail':'Запись уже существует или данные изменились. Обновите список.'},status=409)
    return JsonResponse({'id':obj.pk,'kind':kind,'label':str(obj)},status=201)
