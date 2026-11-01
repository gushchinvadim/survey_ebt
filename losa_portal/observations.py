"""Offline observation journal. The caller holds a lock on the parent audit sheet."""
from uuid import NAMESPACE_URL, uuid5
from rest_framework import serializers
from losa.models import (
    AuditMistake, AuditThreat, AuditSafetyCondition, PhaseOfFlight,
    Mistake, MistakeType, MistakeSection, Threat,
)

THREAT_FIELDS = (
    "threat", "flight_phase", "observed_at", "comment",
    "was_control_effective", "correct_actions",
)
MISTAKE_FIELDS = (
    "mistake", "flight_phase", "observed_at", "comment",
    "who_made", "who_noticed", "reaction", "error_result", "is_action_ok",
)


def event_key(kind, row):
    # Legacy admin rows have no UUID yet. Keep a deterministic ID until first update.
    return row.client_id or uuid5(NAMESPACE_URL, f"losa:{kind}:{row.audit_sheet_id}:{row.pk}")


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError("Переданы неизвестные поля наблюдения.")
        return super().to_internal_value(data)


class BaseEventSerializer(StrictSerializer):
    id = serializers.UUIDField()
    flight_phase = serializers.PrimaryKeyRelatedField(queryset=PhaseOfFlight.objects.all())
    observed_at = serializers.DateTimeField(allow_null=True)
    comment = serializers.CharField(allow_blank=True, trim_whitespace=False)


class ThreatEventSerializer(BaseEventSerializer):
    threat = serializers.PrimaryKeyRelatedField(queryset=Threat.objects.all())
    was_control_effective = serializers.BooleanField(allow_null=True)
    correct_actions = serializers.BooleanField(allow_null=True)


def mistake_choice(field):
    return serializers.ChoiceField(choices=AuditMistake._meta.get_field(field).choices, allow_null=True)


class MistakeEventSerializer(BaseEventSerializer):
    mistake = serializers.PrimaryKeyRelatedField(queryset=Mistake.objects.all())
    who_made = mistake_choice("who_made")
    who_noticed = mistake_choice("who_noticed")
    reaction = mistake_choice("reaction")
    error_result = mistake_choice("error_result")
    is_action_ok = serializers.BooleanField(allow_null=True)
    threat_id = serializers.UUIDField(allow_null=True)
    safety_condition_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), allow_empty=True
    )

    def validate_safety_condition_ids(self, value):
        return sorted(set(value))


class JournalSerializer(StrictSerializer):
    mistakes = MistakeEventSerializer(many=True)
    threats = ThreatEventSerializer(many=True)
    deleted_mistakes = serializers.ListField(child=serializers.UUIDField())
    deleted_threats = serializers.ListField(child=serializers.UUIDField())

    def validate(self, attrs):
        for key in ("mistakes", "threats"):
            ids = [item["id"] for item in attrs[key]]
            deleted = attrs[f"deleted_{key}"]
            if len(ids) != len(set(ids)) or len(deleted) != len(set(deleted)):
                raise serializers.ValidationError("Идентификатор наблюдения повторяется.")
            if set(ids) & set(deleted):
                raise serializers.ValidationError("Нельзя сохранять и удалять одну запись одновременно.")
        return attrs


def catalog(sheet):
    return {
        "phases": [
            {"id": p.pk, "code": p.phase_of_flight, "label": str(p)}
            for p in PhaseOfFlight.objects.order_by("code", "pk")
        ],
        "mistake_types": list(MistakeType.objects.order_by("code").values("id", "code", "name", "describe")),
        "mistake_sections": list(MistakeSection.objects.order_by("type__code", "sort_order", "pk").values(
            "id", "type_id", "name"
        )),
        "mistakes": list(Mistake.objects.order_by("type__code", "code", "pk").values(
            "id", "code", "name", "type_id", "section_id"
        )),
        "threat_types": list(Threat.THREAT_TYPE_CHOICES),
        "threats": list(Threat.objects.order_by("code", "pk").values("id", "code", "type", "describe")),
        "people": list(AuditMistake.MISTAKE_RELAY_CHOICE),
        "reactions": list(AuditMistake.REACTION_CHOICE),
        "results": list(AuditMistake.ERROR_RESULT_CHOICE),
        "safety_conditions": [
            {"id": row.pk, "label": f"{row.condition.code} — {row.condition.name}"}
            for row in AuditSafetyCondition.objects.filter(audit_sheet=sheet).select_related("condition")
        ],
    }


def read(sheet):
    threats = list(AuditThreat.objects.filter(audit_sheet=sheet).order_by("pk"))
    threat_ids = {r.pk: event_key("threat", r) for r in threats}
    def common(row, fields):
        value = {"id": str(event_key("mistake" if isinstance(row, AuditMistake) else "threat", row))}
        for field in fields:
            field_value = getattr(row, f"{field}_id") if field in ("mistake", "threat", "flight_phase") else getattr(row, field)
            if field == "observed_at" and field_value:
                field_value = field_value.isoformat()
            # Optional CharFields created through older paths can contain "".
            if field in ("who_made", "who_noticed", "reaction", "error_result") and field_value == "":
                field_value = None
            value[field] = field_value
        return value
    mistakes = []
    for row in AuditMistake.objects.filter(audit_sheet=sheet).prefetch_related("safety_condition_events").order_by("pk"):
        item = common(row, MISTAKE_FIELDS)
        key = threat_ids.get(row.for_threat_reason_id)
        item["threat_id"] = str(key) if key else None
        item["safety_condition_ids"] = sorted(r.pk for r in row.safety_condition_events.all())
        mistakes.append(item)
    return {
        "mistakes": mistakes,
        "threats": [common(row, THREAT_FIELDS) for row in threats],
        "deleted_mistakes": [], "deleted_threats": [],
    }


def indexes(sheet):
    return {
        "mistakes": {event_key("mistake", r): r for r in AuditMistake.objects.filter(audit_sheet=sheet)},
        "threats": {event_key("threat", r): r for r in AuditThreat.objects.filter(audit_sheet=sheet)},
    }


def validate_for_sheet(sheet, data):
    existing = indexes(sheet)
    for key, model in (("mistakes", AuditMistake), ("threats", AuditThreat)):
        submitted = {item["id"] for item in data[key]} | set(data[f"deleted_{key}"])
        if model.objects.filter(client_id__in=submitted).exclude(audit_sheet=sheet).exists():
            raise serializers.ValidationError("Наблюдение принадлежит другому листу.")
        for item in data[key]:
            if item["id"] not in existing[key] and item["id"].version != 4:
                raise serializers.ValidationError("Для нового наблюдения нужен UUID версии 4.")
    threat_ids = (set(existing["threats"]) | {item["id"] for item in data["threats"]}) - set(data["deleted_threats"])
    safety_ids = set(AuditSafetyCondition.objects.filter(audit_sheet=sheet).values_list("pk", flat=True))
    for item in data["mistakes"]:
        if item["threat_id"] is not None and item["threat_id"] not in threat_ids:
            raise serializers.ValidationError("Связанная угроза отсутствует в этом листе или удаляется.")
        if not set(item["safety_condition_ids"]) <= safety_ids:
            raise serializers.ValidationError("Изменения состояния безопасности должны относиться к этому листу.")
    # Do not delete a mistake still linked to safety records. Detach explicitly first.
    for key in data["deleted_mistakes"]:
        row = existing["mistakes"].get(key)
        if row and row.safety_condition_events.exists():
            raise serializers.ValidationError("Перед удалением ошибки снимите её связи с изменениями состояния безопасности.")
    submitted_mistakes = {item["id"]: item for item in data["mistakes"]}
    removed_mistakes = set(data["deleted_mistakes"])
    for key in data["deleted_threats"]:
        row = existing["threats"].get(key)
        if not row:
            continue
        for mistake in AuditMistake.objects.filter(for_threat_reason=row):
            mistake_key = event_key("mistake", mistake)
            replacement = submitted_mistakes.get(mistake_key)
            if mistake_key not in removed_mistakes and (
                not replacement or replacement["threat_id"] == key
            ):
                raise serializers.ValidationError("Угроза связана с ошибкой. Сначала снимите или измените эту связь.")
    return existing


def same_as_stored(sheet, data):
    stored = JournalSerializer(data=read(sheet))
    if not stored.is_valid():
        return False
    saved = stored.validated_data
    for key in ("mistakes", "threats"):
        rows = {item["id"]: item for item in saved[key]}
        if any(rows.get(item["id"]) != item for item in data[key]):
            return False
        if any(item_id in rows for item_id in data[f"deleted_{key}"]):
            return False
    return True


def save(sheet, data):
    existing = indexes(sheet)
    threats = existing["threats"].copy()
    for item in data["threats"]:
        row = threats.get(item["id"]) or AuditThreat(audit_sheet=sheet)
        row.client_id = item["id"]
        for field in THREAT_FIELDS:
            setattr(row, field, item[field])
        row.save()
        threats[item["id"]] = row
    for item in data["mistakes"]:
        row = existing["mistakes"].get(item["id"]) or AuditMistake(audit_sheet=sheet)
        row.client_id = item["id"]
        for field in MISTAKE_FIELDS:
            setattr(row, field, item[field])
        row.for_threat_reason = threats.get(item["threat_id"]) if item["threat_id"] else None
        row.save()
        row.safety_condition_events.set(item["safety_condition_ids"])
    for key in data["deleted_mistakes"]:
        row = existing["mistakes"].get(key)
        if row:
            row.delete()
    for key in data["deleted_threats"]:
        row = threats.get(key)
        if row:
            row.delete()
