from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from datetime import date
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from losa.models import (Aircraft, Airport, Auditor, Company, Location, Pilot, AuditSheet,
                         AuditThreat, Threat, AuditMistake, Mistake, MistakeType, PhaseOfFlight,
                         AssessmentTemplate, AssessmentStage, AssessmentSection, AssessmentCriterion,
                         AuditCriterionRating, AuditAssessment, FinalMarkCrew)
from .models import Flight, AuditAssignment, PortalProfile
from .access import COORDINATOR_GROUP, AUDITOR_GROUP
from .models import TextObservation, ObservationTopic
from .text_analysis import digest


class TextAnalysisTests(TestCase):
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
        cls.coordinator.is_staff = True
        cls.coordinator.save()
        cls.auditor_user.is_staff = True
        cls.auditor_user.save()
        cls.source = AuditAssessment.objects.get(audit_sheet=cls.sheets[0], stage=cls.stage)
        cls.source.facts = 'Экипаж изучил погоду. КВС проявлял суету. Параметры выставлены поздно.'
        cls.source.save()
        cls.topic = ObservationTopic.objects.get(name='Подготовка и планирование')

    def url(self): return reverse('admin:text-analysis-stage', args=[self.source.pk])
    def values(self, **changes):
        result = dict(source_digest=digest(self.source.facts), quote='Экипаж изучил погоду.',
                      topics=[self.topic.pk], nature='practice', evidence='fact', note='Подготовка')
        result.update(changes)
        return result
    def login(self): self.client.force_login(self.coordinator)
    def create(self, **changes):
        self.login()
        return self.client.post(self.url(), self.values(**changes))

    def test_save_multiple_topics_without_changing_source(self):
        other = ObservationTopic.objects.get(name='Погода и внешние условия')
        response = self.create(topics=[self.topic.pk, other.pk])
        self.assertEqual(response.status_code, 302)
        item = TextObservation.objects.get()
        self.assertEqual(item.topics.count(), 2)
        self.assertEqual(item.created_by, self.coordinator)
        self.assertEqual(item.quote, 'Экипаж изучил погоду.')
        self.source.refresh_from_db()
        self.assertEqual(item.source_snapshot, self.source.facts)
        self.assertEqual(item.audit_sheet_id, self.sheets[0].pk)

    def test_reject_modified_quote_missing_topic_and_duplicate(self):
        self.assertEqual(self.create(quote='Придуманное наблюдение').status_code, 200)
        self.assertFalse(TextObservation.objects.exists())
        self.create(topics=[])
        self.assertFalse(TextObservation.objects.exists())
        self.create()
        self.create()
        self.assertEqual(TextObservation.objects.count(), 1)

    def test_stale_source_rejected_and_existing_snapshot_preserved(self):
        self.create()
        item = TextObservation.objects.get()
        original = item.source_snapshot
        self.source.facts += ' Новое замечание.'
        self.source.save()
        self.assertTrue(item.source_changed)
        response = self.client.post(self.url(), self.values(source_digest=digest(original)))
        self.assertContains(response, 'Текст источника изменился')
        self.assertEqual(TextObservation.objects.count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.source_snapshot, original)

    def test_only_staff_coordinator_can_read_or_write(self):
        self.client.force_login(self.auditor_user)
        for url in [self.url(), reverse('admin:text-analysis-review'), reverse('admin:losa_portal_textobservation_changelist')]:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(self.url(), self.values()).status_code, 403)
        self.assertFalse(TextObservation.objects.exists())
        self.coordinator.is_staff = False
        self.coordinator.save()
        self.client.force_login(self.coordinator)
        self.assertEqual(self.client.get(self.url()).status_code, 302)

    def test_summary_counts_unique_sheets_and_filters_cases(self):
        self.create()
        self.create(quote='КВС проявлял суету.', nature='difficulty', evidence='opinion')
        response = self.client.get(reverse('admin:text-analysis-review'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data['filtered_sheets'], 1)
        row = next(r for r in response.context_data['topic_rows'] if r['topic'] == self.topic)
        self.assertEqual((row['sheets'], row['difficulties'], row['practices'], row['percent']), (1,1,1,100))
        filtered = self.client.get(reverse('admin:text-analysis-review'), {'nature': 'practice', 'q': 'погоду'})
        self.assertEqual(filtered.context_data['event_count'], 1)
        TextObservation.objects.update(status='excluded')
        self.assertEqual(self.client.get(reverse('admin:text-analysis-review')).context_data['event_count'], 0)

    def test_final_notes_and_model_source_integrity(self):
        final = FinalMarkCrew.objects.get(audit_sheet=self.sheets[0])
        final.general_notes = 'Хорошее взаимодействие.'
        final.save()
        self.login()
        response = self.client.post(reverse('admin:text-analysis-final', args=[final.pk]),
            self.values(quote=final.general_notes, source_digest=digest(final.general_notes)))
        self.assertEqual(response.status_code, 302)
        item = TextObservation.objects.get()
        self.assertEqual(item.source_label, 'Общее впечатление')
        item.audit_sheet = self.sheets[1]
        with self.assertRaises(ValidationError): item.full_clean()

    def test_parent_filter_and_cycle_validation(self):
        self.create()
        parent = ObservationTopic.objects.create(name='Родитель')
        self.topic.parent = parent
        self.topic.save()
        response = self.client.get(reverse('admin:text-analysis-review'), {'topic': parent.pk})
        self.assertEqual(response.context_data['event_count'], 1)
        parent.parent = self.topic
        with self.assertRaises(ValidationError): parent.full_clean()

    def test_admin_cards_keep_source_and_quote_read_only(self):
        self.create()
        item = TextObservation.objects.get()
        response = self.client.get(reverse('admin:losa_portal_textobservation_change', args=[item.pk]))
        self.assertEqual(response.status_code, 200)
        form = response.context_data['adminform'].form
        self.assertNotIn('quote', form.fields)
        self.assertNotIn('source_snapshot', form.fields)
        self.assertNotIn('assessment', form.fields)
        self.assertIn('topics', form.fields)

    def test_topic_form_does_not_use_server_side_cursor_iterator(self):
        from unittest.mock import patch
        from django.db.models.query import QuerySet
        from .text_analysis import ExtractForm
        # Django's default ModelChoiceIterator calls .iterator(). Simulate its
        # PostgreSQL named-cursor failure; rendering must not take this path.
        with patch.object(QuerySet, 'iterator', side_effect=RuntimeError('named cursor unavailable')):
            html = ExtractForm().as_p()
        self.assertIn('Подготовка и планирование', html)
        self.assertIn('id_topics', html)
