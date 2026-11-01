"""Draft descent/approach/landing block. All writes are scoped to a locked AuditSheet."""
from rest_framework import serializers
from losa.models import (
    DescentApproach, TypeApproachAndWeather, StabilizedApproachAssessment,
    Landing, RolloutAndTaxingAndParking,
)

DESCENT_FIELDS = (
    "ten_thousand_brief", "start_of_descent", "descent_trajectory",
    "describe_deviation", "approach_mode", "flap_settings",
)
CONDITION_FIELDS = ("approach_type", "visual_condition")
MEASUREMENT_FIELDS = (
    "speed_deviation", "rate_of_descent_deviation", "thrust_settings", "landing_config",
    "course_deviation", "course_more_than", "glideslope_deviation", "glideslope_more_than",
)
LANDING_FIELDS = ("threshold_height", "flare_and_touch_distance", "g_load")
ROLLOUT_FIELDS = ("thrust_reverser_on", "thrust_reverser_off", "taxi_speed", "taxi_speed_turn", "parking")
STAGES = tuple(code for code, _ in StabilizedApproachAssessment.STAGE_CHOICES)


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError("Переданы неизвестные поля блока.")
        return super().to_internal_value(data)


def choice(model, field):
    return serializers.ChoiceField(
        choices=model._meta.get_field(field).choices, allow_null=True,
    )


class DescentSerializer(StrictSerializer):
    ten_thousand_brief = choice(DescentApproach, "ten_thousand_brief")
    start_of_descent = choice(DescentApproach, "start_of_descent")
    descent_trajectory = choice(DescentApproach, "descent_trajectory")
    describe_deviation = serializers.CharField(allow_blank=True, trim_whitespace=False)
    approach_mode = choice(DescentApproach, "approach_mode")
    flap_settings = choice(DescentApproach, "flap_settings")


class ConditionsSerializer(StrictSerializer):
    # Empty type is permitted while drafting, as for other unfinished sheet fields.
    approach_type = serializers.ChoiceField(
        choices=TypeApproachAndWeather.APPROACH_TYPE_CHOICES, allow_blank=True
    )
    visual_condition = choice(TypeApproachAndWeather, "visual_condition")


class MeasurementSerializer(StrictSerializer):
    speed_deviation = serializers.IntegerField(
        allow_null=True, min_value=-2147483648, max_value=2147483647
    )
    rate_of_descent_deviation = choice(StabilizedApproachAssessment, "rate_of_descent_deviation")
    thrust_settings = choice(StabilizedApproachAssessment, "thrust_settings")
    landing_config = choice(StabilizedApproachAssessment, "landing_config")
    course_deviation = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, allow_null=True
    )
    course_more_than = serializers.BooleanField()
    glideslope_deviation = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, allow_null=True
    )
    glideslope_more_than = serializers.BooleanField()

    def validate(self, attrs):
        for field in ("course", "glideslope"):
            if attrs[f"{field}_more_than"] and attrs[f"{field}_deviation"] is None:
                raise serializers.ValidationError({
                    f"{field}_deviation": "Укажите значение для признака «более»."
                })
        return attrs


class LandingSerializer(StrictSerializer):
    threshold_height = choice(Landing, "threshold_height")
    flare_and_touch_distance = choice(Landing, "flare_and_touch_distance")
    g_load = choice(Landing, "g_load")


class RolloutSerializer(StrictSerializer):
    thrust_reverser_on = choice(RolloutAndTaxingAndParking, "thrust_reverser_on")
    thrust_reverser_off = choice(RolloutAndTaxingAndParking, "thrust_reverser_off")
    taxi_speed = choice(RolloutAndTaxingAndParking, "taxi_speed")
    taxi_speed_turn = choice(RolloutAndTaxingAndParking, "taxi_speed_turn")
    parking = choice(RolloutAndTaxingAndParking, "parking")


class ApproachSerializer(StrictSerializer):
    descent = DescentSerializer()
    conditions = ConditionsSerializer()
    measurements = serializers.DictField(child=MeasurementSerializer())
    landing = LandingSerializer()
    rollout = RolloutSerializer()

    def validate_measurements(self, value):
        if set(value) != set(STAGES):
            raise serializers.ValidationError("Нужны три этапа: вход в глиссаду, 1000 и 500 футов.")
        return value


def catalog():
    def choices(model, fields):
        return {
            field: list(model._meta.get_field(field).choices)
            for field in fields if model._meta.get_field(field).choices
        }
    return {
        "stages": list(StabilizedApproachAssessment.STAGE_CHOICES),
        "descent": choices(DescentApproach, DESCENT_FIELDS),
        "conditions": choices(TypeApproachAndWeather, CONDITION_FIELDS),
        "measurements": choices(StabilizedApproachAssessment, MEASUREMENT_FIELDS),
        "landing": choices(Landing, LANDING_FIELDS),
        "rollout": choices(RolloutAndTaxingAndParking, ROLLOUT_FIELDS),
    }


def empty_measurement():
    return {
        field: False if field.endswith("_more_than") else None
        for field in MEASUREMENT_FIELDS
    }


def row_values(model, sheet, fields, defaults):
    row = model.objects.filter(audit_sheet=sheet).first()
    return {field: getattr(row, field) for field in fields} if row else defaults


def read(sheet):
    measurements = {stage: empty_measurement() for stage in STAGES}
    for row in StabilizedApproachAssessment.objects.filter(audit_sheet=sheet, stage__in=STAGES):
        measurements[row.stage] = {field: getattr(row, field) for field in MEASUREMENT_FIELDS}
    return {
        "descent": row_values(DescentApproach, sheet, DESCENT_FIELDS, {
            field: "" if field == "describe_deviation" else None for field in DESCENT_FIELDS
        }),
        "conditions": row_values(TypeApproachAndWeather, sheet, CONDITION_FIELDS, {
            "approach_type": "", "visual_condition": None
        }),
        "measurements": measurements,
        "landing": row_values(Landing, sheet, LANDING_FIELDS, dict.fromkeys(LANDING_FIELDS)),
        "rollout": row_values(RolloutAndTaxingAndParking, sheet, ROLLOUT_FIELDS, dict.fromkeys(ROLLOUT_FIELDS)),
    }


def same_as_stored(sheet, data):
    # Convert stored Decimal/JSON strings and choices through the same validators.
    stored = ApproachSerializer(data=read(sheet))
    return stored.is_valid() and stored.validated_data == data


def has_values(data):
    return any(value is not None and value != "" and value is not False for value in data.values())


def save(sheet, data):
    for model, key in (
        (DescentApproach, "descent"), (TypeApproachAndWeather, "conditions"),
        (Landing, "landing"), (RolloutAndTaxingAndParking, "rollout"),
    ):
        values = data[key]
        if has_values(values) or model.objects.filter(audit_sheet=sheet).exists():
            model.objects.update_or_create(audit_sheet=sheet, defaults=values)
    for stage, values in data["measurements"].items():
        if has_values(values) or StabilizedApproachAssessment.objects.filter(
            audit_sheet=sheet, stage=stage
        ).exists():
            # Existing per-stage comments, not part of this UI, are preserved.
            StabilizedApproachAssessment.objects.update_or_create(
                audit_sheet=sheet, stage=stage, defaults=values
            )
