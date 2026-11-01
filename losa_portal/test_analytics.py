from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from losa.models import (Aircraft, Airport, Auditor, Company, Location, Pilot, AuditSheet,
                         AuditThreat, Threat, AuditMistake, Mistake, MistakeType, PhaseOfFlight,
                         AssessmentTemplate, AssessmentStage, AssessmentSection, AssessmentCriterion,
                         AuditCriterionRating, AuditAssessment, FinalMarkCrew)
from .models import Flight, AuditAssignment, PortalProfile
from .access import COORDINATOR_GROUP, AUDITOR_GROUP


class AnalyticsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.coordinator = get_user_model().objects.create_user('analytics-coordinator')
        cls.coordinator.groups.add(Group.objects.create(name=COORDINATOR_GROUP))
        cls.auditor = Auditor.objects.create(auditor_code=1, name='Private auditor')
        cls.auditor_user = get_user_model().objects.create_user('analytics-auditor')
        cls.auditor_user.groups.add(Group.objects.create(name=AUDITOR_GROUP))
        PortalProfile.objects.create(user=cls.auditor_user, auditor=cls.auditor)
        loc = Location.objects.create(location_name='Base', location_code='B')
        company = Company.objects.create(company_name='Company', company_code='C')
        cls.cap = Pilot.objects.create(pilot_id=101, position='CAPT', company=company, location=loc)
        cls.fo = Pilot.objects.create(pilot_id=102, position='FO', company=company, location=loc)
        cls.aircraft = Aircraft.objects.create(aircraft_type='Test aircraft')
        airport = Airport.objects.create(airport_code='AAA', airport_name='Airport')
        cls.flight = Flight.objects.create(number='100', departure=airport, arrival=airport, aircraft=cls.aircraft, time='12:00')
        cls.sheets = []
        for i, status in enumerate(['completed', 'completed', 'scheduled']):
            sheet = AuditSheet.objects.create(audit_number=f'TEST-{i}', date=date(2019, 1, i+1),
                auditor=cls.auditor, aircraft=cls.aircraft, captain=cls.cap, first_officer=cls.fo,
                departure=airport, arrival=airport, actual_arrival='BBB' if i == 0 else '')
            AuditAssignment.objects.create(date=date(2026, 1, i+1), flight=cls.flight,
                captain=cls.cap, first_officer=cls.fo, auditor=cls.auditor,
                created_by=cls.coordinator, audit_sheet=sheet, status=status)
            cls.sheets.append(sheet)
        cls.phase = PhaseOfFlight.objects.get_or_create(phase_of_flight='approach')[0]
        threat = Threat.objects.create(code='50', type='atc', describe='ATC threat')
        cls.events = []
        for i, sheet in enumerate([cls.sheets[0], cls.sheets[0], cls.sheets[1], cls.sheets[2]]):
            cls.events.append(AuditThreat.objects.create(audit_sheet=sheet, threat=threat, flight_phase=cls.phase,
                was_control_effective=[True, False, None, True][i], correct_actions=True))
        mt = MistakeType.objects.get_or_create(code='5', defaults={'name': 'Decision'})[0]
        mistake = Mistake.objects.get_or_create(code='502', defaults={'name': 'Deviation', 'type': mt})[0]
        AuditMistake.objects.create(audit_sheet=cls.sheets[0], mistake=mistake, flight_phase=cls.phase,
            who_noticed='CAPT', reaction='1', error_result='1', is_action_ok=True, for_threat_reason=cls.events[0])
        AuditMistake.objects.create(audit_sheet=cls.sheets[1], mistake=mistake, flight_phase=cls.phase)
        template = AssessmentTemplate.objects.create(name='Template', version='v1')
        section = AssessmentSection.objects.create(template=template, number=1, name='Execution')
        criterion = AssessmentCriterion.objects.create(section=section, code='1', name='Monitoring')
        cls.stage = AssessmentStage.objects.update_or_create(code='preflight', defaults={'name': 'Preflight', 'template': template})[0]
        cls.empty_stage = AssessmentStage.objects.update_or_create(code='cruise', defaults={'name': 'Cruise', 'template': None})[0]
        AuditCriterionRating.objects.create(audit_sheet=cls.sheets[0], stage=cls.stage, criterion=criterion, score=2)
        AuditCriterionRating.objects.create(audit_sheet=cls.sheets[1], stage=cls.stage, criterion=criterion, score=None)
        AuditAssessment.objects.create(audit_sheet=cls.sheets[0], stage=cls.stage, facts='Facts for drilldown')
        FinalMarkCrew.objects.create(audit_sheet=cls.sheets[0], total_general_mark=3)

    def get_data(self, **params):
        self.client.force_login(self.coordinator)
        response = self.client.get('/api/analytics/', params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_event_counts_are_distinct_from_sheet_counts_and_nulls(self):
        data = self.get_data()
        self.assertEqual(data['summary']['sheets'], 2)
        self.assertEqual(data['summary']['threats'], 3)
        self.assertEqual(data['groups']['threat_codes'][0]['sheets'], 2)
        self.assertEqual({r['label']: r['count'] for r in data['groups']['effective']}, {'Да': 1, 'Нет': 1, 'Не указано': 1})
        self.assertEqual(data['errors'][0]['threat'], '50 — ATC threat')
        self.assertEqual(data['errors'][1]['threat'], 'Не указано')
        self.assertEqual(data['errors'][1]['noticed'], 'Не указано')

    def test_uses_actual_sheet_date_and_route_and_draft_filter(self):
        data = self.get_data(**{'from': '2019-01-01', 'to': '2019-01-01', 'route': 'AAA → BBB'})
        self.assertEqual(data['summary']['sheets'], 1)
        self.assertEqual(data['summary']['threats'], 2)
        self.assertEqual(self.get_data(status='draft')['summary']['sheets'], 1)
        self.assertEqual(self.get_data(status='all')['summary']['sheets'], 3)
        self.assertEqual(self.get_data(aircraft='999999')['summary']['sheets'], 0)

    def test_ratings_include_facts_and_keep_saved_null_separate(self):
        data = self.get_data()
        group = next(r for r in data['rating_groups'] if r['stage'] == 'Preflight')
        self.assertEqual(group['scores'], [0, 1, 0, 0])
        self.assertEqual(group['missing_saved'], 1)
        self.assertEqual(data['summary']['scores'], 2)
        self.assertEqual(data['ratings'][0]['facts'], 'Facts for drilldown')
        self.assertIn('Cruise', data['quality']['stages_without_criteria'])

    def test_permissions_and_read_only(self):
        self.assertEqual(self.client.get('/api/analytics/').status_code, 401)
        self.client.force_login(self.auditor_user)
        self.assertEqual(self.client.get('/api/analytics/').status_code, 403)
        self.client.force_login(self.coordinator)
        self.assertEqual(self.client.post('/api/analytics/').status_code, 405)
        before = list(AuditAssignment.objects.values_list('status', flat=True))
        self.get_data()
        self.assertEqual(before, list(AuditAssignment.objects.values_list('status', flat=True)))

    def test_invalid_filters_and_no_pilot_identities(self):
        self.client.force_login(self.coordinator)
        for params in [{'from': 'bad'}, {'from': '2020-01-01', 'to': '2019-01-01'}, {'status': 'unknown'}, {'aircraft': 'bad'}]:
            self.assertEqual(self.client.get('/api/analytics/', params).status_code, 400)
        data = self.get_data()
        self.assertFalse(any('captain' in r or 'first_officer' in r or 'auditor' in r for r in data['sheets']))
        self.assertEqual(self.get_data(**{'from': '2030-01-01'})['summary']['sheets'], 0)

    def test_template_changes_do_not_merge_historical_ratings(self):
        template = AssessmentTemplate.objects.create(name='New', version='v2')
        section = AssessmentSection.objects.create(template=template, number=1, name='Execution')
        criterion = AssessmentCriterion.objects.create(section=section, code='1', name='Monitoring')
        AuditCriterionRating.objects.create(audit_sheet=self.sheets[1], stage=self.stage, criterion=criterion, score=4)
        data = self.get_data()
        groups = [r for r in data['rating_groups'] if r['stage'] == 'Preflight']
        self.assertEqual(len(groups), 2)
        self.assertEqual({r['template'] for r in groups}, {'v1', 'v2'})
