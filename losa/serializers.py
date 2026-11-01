from rest_framework import serializers
from .models import (
    Location,
    Company,
    Pilot,
    Auditor,
    Aircraft,
    Airport,
    MistakeType,
    MistakeSection,
    Mistake,
    Threat,
    AuditSheet,
    PhaseOfFlight,
    ChangingSafetyConditionSheet,
    AuditMistake,
    AuditSafetyCondition,
    AuditThreat,
    AssessmentStage,
    AssessmentTemplate,
    AssessmentSection,
    AssessmentCriterion,
    AuditAssessment,
    AuditCriterionRating,
    StabilizedApproachAssessment,
    TypeApproachAndWeather,
    FinalMarkCrew, DescentApproach, RolloutAndTaxingAndParking, Landing,
)


class LocationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Location
        fields = ("id", "location_name", "location_code", "address")
        read_only_fields = ("id",)


class CompanySerializer(serializers.ModelSerializer):

    class Meta:
        model = Company
        fields = ("id", "company_name", "company_code")
        read_only_fields = ("id",)


class PilotSerializer(serializers.ModelSerializer):

    class Meta:
        model = Pilot
        fields = (
            "id",
            "pilot_id",
            "company",
            "location",
            "position",
            "experience",
            "type_experience",
            "fmc_experience",
        )
        read_only_fields = ("id",)


class AuditorSerializer(serializers.ModelSerializer):

    class Meta:
        model = Auditor
        fields = ("id", "auditor_code", "name")
        read_only_fields = ("id",)


class AircraftSerializer(serializers.ModelSerializer):

    class Meta:
        model = Aircraft
        fields = ("id", "aircraft_type")
        read_only_fields = ("id",)


class AirportSerializer(serializers.ModelSerializer):

    class Meta:
        model = Airport
        fields = ("id", "airport_code", "airport_name")
        read_only_fields = ("id",)


class MistakeTypeSerializer(serializers.ModelSerializer):

    class Meta:
        model = MistakeType
        fields = ("id", "code", "name", "describe")
        read_only_fields = ("id",)


class MistakeSectionSerializer(serializers.ModelSerializer):
    type_code = serializers.CharField(source="type.code", read_only=True, default=None)
    type_name = serializers.CharField(source="type.name", read_only=True, default=None)

    class Meta:
        model = MistakeSection
        fields = ("id", "type", "name", "sort_order", "type_code", "type_name")
        read_only_fields = ("id",)


class MistakeSerializer(serializers.ModelSerializer):
    type_code = serializers.CharField(source="type.code", read_only=True, default=None)
    type_name = serializers.CharField(source="type.name", read_only=True, default=None)
    type_description = serializers.CharField(
        source="type.describe", read_only=True, default=None
    )
    section_name = serializers.CharField(
        source="section.name", read_only=True, default=None
    )

    def validate(self, attrs):
        kind = attrs.get("type", getattr(self.instance, "type", None))
        section = attrs.get("section", getattr(self.instance, "section", None))
        if section and kind and (section.type_id != kind.pk):
            raise serializers.ValidationError(
                {"section": "Раздел относится к другому типу ошибки."}
            )
        return attrs

    class Meta:
        model = Mistake
        fields = (
            "id",
            "code",
            "name",
            "type",
            "section",
            "type_code",
            "type_name",
            "type_description",
            "section_name",
        )
        read_only_fields = ("id",)


class ThreatSerializer(serializers.ModelSerializer):
    type_name = serializers.CharField(
        source="get_type_display", read_only=True, default=None
    )

    class Meta:
        model = Threat
        fields = ("id", "code", "type", "describe", "type_name")
        read_only_fields = ("id",)


class PhaseOfFlightSerializer(serializers.ModelSerializer):
    phase_label = serializers.CharField(
        source="get_phase_of_flight_display", read_only=True, default=None
    )

    class Meta:
        model = PhaseOfFlight
        fields = ("id", "code", "phase_of_flight", "phase_label")
        read_only_fields = ("id",)


class ChangingSafetyConditionSheetSerializer(serializers.ModelSerializer):
    section_name = serializers.CharField(
        source="get_section_display", read_only=True, default=None
    )

    class Meta:
        model = ChangingSafetyConditionSheet
        fields = ("id", "code", "section", "name", "section_name")
        read_only_fields = ("id",)


class AuditMistakeSerializer(serializers.ModelSerializer):

    def validate(self, attrs):
        sheet = attrs.get("audit_sheet", getattr(self.instance, "audit_sheet", None))
        threat = attrs.get(
            "for_threat_reason", getattr(self.instance, "for_threat_reason", None)
        )
        if sheet and threat and (sheet.pk != threat.audit_sheet_id):
            raise serializers.ValidationError(
                {"for_threat_reason": "Угроза должна относиться к этому листу."}
            )
        return attrs

    class Meta:
        model = AuditMistake
        fields = (
            "id",
            "client_id",
            "audit_sheet",
            "mistake",
            "observed_at",
            "flight_phase",
            "who_made",
            "who_noticed",
            "reaction",
            "error_result",
            "for_threat_reason",
            "is_action_ok",
            "code_csc",
            "who_identified_changing",
            "crew_reaction",
            "changing_result",
            "comment",
        )
        read_only_fields = (
            "id",
            "client_id",
            "code_csc",
            "who_identified_changing",
            "crew_reaction",
            "changing_result",
        )


class AuditSafetyConditionSerializer(serializers.ModelSerializer):

    def validate(self, attrs):
        sheet = attrs.get("audit_sheet", getattr(self.instance, "audit_sheet", None))
        mistakes = attrs.get("mistakes")
        if mistakes is None and self.instance is not None:
            mistakes = self.instance.mistakes.all()
        if (
            sheet
            and mistakes is not None
            and any((m.audit_sheet_id != sheet.pk for m in mistakes))
        ):
            raise serializers.ValidationError(
                {"mistakes": "Ошибки должны относиться к этому листу."}
            )
        return attrs

    class Meta:
        model = AuditSafetyCondition
        fields = (
            "id",
            "audit_sheet",
            "condition",
            "observed_at",
            "flight_phase",
            "mistakes",
            "who_identified",
            "crew_reaction",
            "result",
            "comment",
        )
        read_only_fields = ("id",)


class AuditThreatSerializer(serializers.ModelSerializer):

    class Meta:
        model = AuditThreat
        fields = (
            "id",
            "client_id",
            "audit_sheet",
            "threat",
            "observed_at",
            "flight_phase",
            "comment",
            "was_control_effective",
            "correct_actions",
        )
        read_only_fields = ("id", "client_id")


class AssessmentStageSerializer(serializers.ModelSerializer):

    class Meta:
        model = AssessmentStage
        fields = ("id", "code", "name", "sort_order", "template")
        read_only_fields = ("id",)


class AssessmentCriterionSerializer(serializers.ModelSerializer):

    class Meta:
        model = AssessmentCriterion
        fields = ("id", "section", "code", "name", "sort_order")
        read_only_fields = ("id",)


class AuditAssessmentSerializer(serializers.ModelSerializer):

    class Meta:
        model = AuditAssessment
        fields = ("id", "audit_sheet", "stage", "facts")
        read_only_fields = ("id",)


class AuditCriterionRatingSerializer(serializers.ModelSerializer):

    class Meta:
        model = AuditCriterionRating
        fields = ("id", "audit_sheet", "criterion", "stage", "score", "comment")
        read_only_fields = ("id",)


class StabilizedApproachAssessmentSerializer(serializers.ModelSerializer):
    stage_name = serializers.CharField(
        source="get_stage_display",
        read_only=True,
    )
    rate_of_descent_deviation_label = serializers.CharField(
        source="get_rate_of_descent_deviation_display",
        read_only=True,
    )
    thrust_settings_label = serializers.CharField(
        source="get_thrust_settings_display",
        read_only=True,
    )
    landing_config_label = serializers.CharField(
        source="get_landing_config_display",
        read_only=True,
    )

    class Meta:
        model = StabilizedApproachAssessment
        fields = (
            "id",
            "audit_sheet",
            "stage",
            "stage_name",
            "speed_deviation",
            "rate_of_descent_deviation",
            "rate_of_descent_deviation_label",
            "thrust_settings",
            "thrust_settings_label",
            "landing_config",
            "landing_config_label",
            "course_deviation",
            "course_more_than",
            "glideslope_deviation",
            "glideslope_more_than",
            "comment",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        for value_field, flag_field in (
            ("course_deviation", "course_more_than"),
            ("glideslope_deviation", "glideslope_more_than"),
        ):
            value = attrs.get(
                value_field,
                getattr(self.instance, value_field, None),
            )
            flag = attrs.get(
                flag_field,
                getattr(self.instance, flag_field, False),
            )

            if value is not None and value < 0:
                raise serializers.ValidationError({
                    value_field: "Значение не может быть отрицательным.",
                })

            if flag and value is None:
                raise serializers.ValidationError({
                    value_field: "Укажите значение для признака «более».",
                })

        return attrs


class AssessmentSectionSerializer(serializers.ModelSerializer):
    criteria = AssessmentCriterionSerializer(many=True, read_only=True)

    class Meta:
        model = AssessmentSection
        fields = ("id", "template", "number", "name", "criteria")
        read_only_fields = ("id",)


class AssessmentTemplateSerializer(serializers.ModelSerializer):
    sections = AssessmentSectionSerializer(many=True, read_only=True)

    class Meta:
        model = AssessmentTemplate
        fields = ("id", "name", "version", "sections")
        read_only_fields = ("id",)


class TypeApproachAndWeatherSerializer(serializers.ModelSerializer):
    approach_type_name = serializers.CharField(
        source="get_approach_type_display", read_only=True
    )
    visual_condition_name = serializers.SerializerMethodField()

    class Meta:
        model = TypeApproachAndWeather
        fields = (
            "id",
            "audit_sheet",
            "approach_type",
            "approach_type_name",
            "visual_condition",
            "visual_condition_name",
        )
        read_only_fields = ("id",)

    def get_visual_condition_name(self, obj):
        if not obj.visual_condition:
            return None
        return obj.get_visual_condition_display()


class FinalMarkCrewSerializer(serializers.ModelSerializer):
    preflight_brief_name = serializers.SerializerMethodField()

    class Meta:
        model = FinalMarkCrew
        fields = (
            "id",
            "audit_sheet",
            "preflight_brief_with_fa",
            "preflight_brief_name",
            "free_communication",
            "capt_as_leader",
            "general_mark_capt",
            "general_mark_copilot",
            "total_general_mark",
            "general_notes",
        )
        read_only_fields = ("id",)

    def get_preflight_brief_name(self, obj):
        if not obj.preflight_brief_with_fa:
            return None
        return obj.get_preflight_brief_with_fa_display()

class DescentApproachSerializer(serializers.ModelSerializer):
    ten_thousand_brief_label = serializers.CharField(
        source="get_ten_thousand_brief_display",
        read_only=True,
    )
    start_of_descent_label = serializers.CharField(
        source="get_start_of_descent_display",
        read_only=True,
    )
    descent_trajectory_label = serializers.CharField(
        source="get_descent_trajectory_display",
        read_only=True,
    )
    approach_mode_label = serializers.CharField(
        source="get_approach_mode_display",
        read_only=True,
    )
    flap_settings_label = serializers.CharField(
        source="get_flap_settings_display",
        read_only=True,
    )

    class Meta:
        model = DescentApproach
        fields = (
            "id",
            "audit_sheet",
            "ten_thousand_brief",
            "ten_thousand_brief_label",
            "start_of_descent",
            "start_of_descent_label",
            "descent_trajectory",
            "descent_trajectory_label",
            "describe_deviation",
            "approach_mode",
            "approach_mode_label",
            "flap_settings",
            "flap_settings_label",
        )
        read_only_fields = ("id",)

class LandingSerializer(serializers.ModelSerializer):
    threshold_height_label = serializers.CharField(
        source="get_threshold_height_display",
        read_only=True,
    )
    flare_and_touch_distance_label = serializers.CharField(
        source="get_flare_and_touch_distance_display",
        read_only=True,
    )
    g_load_label = serializers.CharField(
        source="get_g_load_display",
        read_only=True,
    )

    class Meta:
        model = Landing
        fields = (
            "id",
            "audit_sheet",
            "threshold_height",
            "threshold_height_label",
            "flare_and_touch_distance",
            "flare_and_touch_distance_label",
            "g_load",
            "g_load_label",
        )
        read_only_fields = ("id",)


class RolloutAndTaxingAndParkingSerializer(serializers.ModelSerializer):
    thrust_reverser_on_label = serializers.CharField(
        source="get_thrust_reverser_on_display",
        read_only=True,
    )
    thrust_reverser_off_label = serializers.CharField(
        source="get_thrust_reverser_off_display",
        read_only=True,
    )
    taxi_speed_label = serializers.CharField(
        source="get_taxi_speed_display",
        read_only=True,
    )
    taxi_speed_turn_label = serializers.CharField(
        source="get_taxi_speed_turn_display",
        read_only=True,
    )
    parking_label = serializers.CharField(
        source="get_parking_display",
        read_only=True,
    )

    class Meta:
        model = RolloutAndTaxingAndParking
        fields = (
            "id",
            "audit_sheet",
            "thrust_reverser_on",
            "thrust_reverser_on_label",
            "thrust_reverser_off",
            "thrust_reverser_off_label",
            "taxi_speed",
            "taxi_speed_label",
            "taxi_speed_turn",
            "taxi_speed_turn_label",
            "parking",
            "parking_label",
        )
        read_only_fields = ("id",)


class AuditSheetSerializer(serializers.ModelSerializer):
    mistake_events = AuditMistakeSerializer(many=True, read_only=True)
    threat_events = AuditThreatSerializer(many=True, read_only=True)
    criterion_ratings = AuditCriterionRatingSerializer(many=True, read_only=True)
    assessments = AuditAssessmentSerializer(many=True, read_only=True)
    stabilized_approach_assessments = StabilizedApproachAssessmentSerializer(
        many=True, read_only=True
    )
    safety_condition_events = AuditSafetyConditionSerializer(many=True, read_only=True)
    approach_conditions = TypeApproachAndWeatherSerializer(read_only=True)
    final_crew_mark = FinalMarkCrewSerializer(read_only=True)
    descent_approach = DescentApproachSerializer(read_only=True)
    landing_assessment = LandingSerializer(read_only=True)

    rollout_taxing_assessment = RolloutAndTaxingAndParkingSerializer(
        read_only=True,
    )

    class Meta:
        model = AuditSheet
        fields = (
            "id",
            "audit_number",
            "date",
            "auditor",
            "aircraft",
            "captain",
            "first_officer",
            "second_officer",
            "flight_engineer",
            "departure",
            "arrival",
            "working_together",
            "final_crew_mark",
            "mistake_events",
            "threat_events",
            "criterion_ratings",
            "assessments",
            "stabilized_approach_assessments",
            "safety_condition_events",
            "leg_number",
            "pilot_flying",
            "is_delay",
            "delay",
            "approach_conditions",
            "captain_experience",
            "captain_type_experience",
            "first_officer_experience",
            "first_officer_type_experience",
            "actual_departure",
            "actual_arrival",
            "demography_revision",
            "descent_approach",
            "landing_assessment",
            "rollout_taxing_assessment",
        )
        read_only_fields = ("id", "demography_revision")

    def validate(self, attrs):
        delayed = attrs.get("is_delay", getattr(self.instance, "is_delay", False))
        minutes = attrs.get("delay", getattr(self.instance, "delay", None))
        if not delayed and minutes not in (None, 0):
            raise serializers.ValidationError(
                {
                    "delay": "Указана длительность задержки, но признак задержки выключен."
                }
            )
        if delayed and minutes == 0:
            raise serializers.ValidationError(
                {
                    "delay": "При наличии задержки укажите число минут больше нуля или оставьте поле пустым до уточнения."
                }
            )
        return attrs

