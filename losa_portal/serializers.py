from rest_framework import serializers

from .access import AUDITOR_GROUP, can_start, can_view
from .models import AuditAssignment, Flight
from losa.models import Auditor, Pilot


class AssignmentSerializer(serializers.ModelSerializer):
    flight_number = serializers.CharField(source="flight.number", read_only=True)
    planned_departure = serializers.CharField(source="flight.departure.airport_code", read_only=True)
    planned_arrival = serializers.CharField(source="flight.arrival.airport_code", read_only=True)
    flight = serializers.PrimaryKeyRelatedField(
        queryset=Flight.objects.filter(is_active=True)
    )
    captain = serializers.PrimaryKeyRelatedField(queryset=Pilot.objects.all())
    first_officer = serializers.PrimaryKeyRelatedField(queryset=Pilot.objects.all())
    auditor = serializers.PrimaryKeyRelatedField(
        queryset=Auditor.objects.filter(
            portal_profile__user__is_active=True,
            portal_profile__user__groups__name=AUDITOR_GROUP,
        ).distinct()
    )
    can_start = serializers.SerializerMethodField()
    can_view = serializers.SerializerMethodField()
    audit_number = serializers.CharField(read_only=True)
    has_sheet = serializers.SerializerMethodField()

    class Meta:
        model = AuditAssignment
        fields = (
            "audit_number",
            "has_sheet",
            "id",
            "date",
            "flight",
            "flight_number",
            "planned_departure",
            "planned_arrival",
            "captain",
            "first_officer",
            "auditor",
            "status",
            "can_start",
            "can_view",
        )
        read_only_fields = ("id", "status")

    def get_can_view(self, obj):
        return can_view(obj, self.context["request"].user)

    def get_can_start(self, obj):
        return can_start(obj, self.context["request"].user)

    def get_has_sheet(self, obj):
        return obj.audit_sheet_id is not None

    def validate(self, attrs):
        captain = attrs.get("captain", getattr(self.instance, "captain", None))
        officer = attrs.get(
            "first_officer", getattr(self.instance, "first_officer", None)
        )
        if captain is not None and captain == officer:
            raise serializers.ValidationError("КВС и второй пилот должны быть разными.")
        return attrs
