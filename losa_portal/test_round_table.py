from django.test import TestCase, Client
from . import test_text_analysis
from .models import RoundTableCycle, SourceReview, TextObservation
from .text_analysis import digest
from losa.models import AuditAssessment, FinalMarkCrew


class RoundTableTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        test_text_analysis.TextAnalysisTests.setUpTestData.__func__(cls)
        cls.coordinator.is_staff=False;cls.coordinator.save()

    def setUp(self): self.client.force_login(self.coordinator)
    def create_cycle(self):
        response=self.client.post('/api/round-table/',{'name':'Первый цикл','assignments':[str(self.sheets[0].portal_assignment.pk)]},content_type='application/json')
        self.assertEqual(response.status_code,201,response.content)
        return response.json()['id']
    def path(self,c,kind='stage',pk=None): return f'/api/round-table/{c}/{kind}/{pk or self.source.pk}/'
    def decision(self,c,decision='confirmed',text=None,revision=0):
        self.source.refresh_from_db()
        return self.client.put(self.path(c),{'decision':decision,'agreed_text':text if text is not None else self.source.facts,
            'note':'Обсуждено аудиторами','revision':revision,'source_digest':digest(self.source.facts)},content_type='application/json')
    def annotate(self,c,quote=None,revision=1):
        return self.client.post(self.path(c)+'observations/',{'quote':quote or 'Экипаж изучил погоду.',
            'topics':[self.topic.pk],'nature':'practice','evidence':'fact','note':'','revision':revision},content_type='application/json')

    def test_coordinator_without_admin_and_completed_membership(self):
        self.assertFalse(self.coordinator.is_staff)
        c=self.create_cycle()
        self.assertEqual(self.client.get(f'/api/round-table/{c}/').status_code,200)
        self.assertEqual(self.client.get(self.path(c)).status_code,200)
        response=self.client.post('/api/round-table/',{'name':'Draft','assignments':[str(self.sheets[2].portal_assignment.pk)]},content_type='application/json')
        self.assertEqual(response.status_code,400)
        self.assertEqual(RoundTableCycle.objects.count(),1)

    def test_auditor_cannot_read_or_write(self):
        c=self.create_cycle()
        self.client.force_login(self.auditor_user)
        for path in ['/api/round-table/',f'/api/round-table/{c}/',self.path(c)]:
            self.assertEqual(self.client.get(path).status_code,403)
        self.assertEqual(self.decision(c).status_code,403)
        self.assertEqual(self.annotate(c).status_code,403)

    def test_confirmation_and_revised_text_preserve_original(self):
        c=self.create_cycle();original=self.source.facts
        self.assertEqual(self.decision(c).status_code,200)
        review=SourceReview.objects.get()
        self.assertEqual(review.agreed_text,original)
        self.assertEqual(self.decision(c,'revised','Согласованный текст.',1).status_code,200)
        self.source.refresh_from_db();review.refresh_from_db()
        self.assertEqual(self.source.facts,original)
        self.assertEqual(review.agreed_text,'Согласованный текст.')
        self.assertEqual(review.revision,2)
        self.assertEqual(review.history[0]['agreed_text'],original)
        self.assertEqual(review.history[0]['revision'],1)
        self.assertEqual(self.annotate(c,'Согласованный текст.',2).status_code,201)
        item=TextObservation.objects.get()
        self.assertFalse(item.source_changed)
        self.assertEqual(item.source_snapshot,'Согласованный текст.')

    def test_pending_and_revision_conflicts(self):
        c=self.create_cycle()
        self.assertEqual(self.annotate(c).status_code,409)
        self.assertEqual(self.decision(c,'pending').status_code,200)
        self.assertEqual(self.annotate(c).status_code,409)
        self.assertEqual(self.decision(c,revision=0).status_code,409)
        self.assertEqual(self.decision(c,revision=1).status_code,200)
        self.assertEqual(self.annotate(c,revision=1).status_code,409)
        self.assertEqual(self.annotate(c,revision=2).status_code,201)

    def test_stale_quote_excluded_and_duplicate_guard(self):
        c=self.create_cycle();self.decision(c)
        self.assertEqual(self.annotate(c).status_code,201)
        self.assertEqual(self.annotate(c).status_code,400)
        data=self.client.get(f'/api/round-table/{c}/').json()
        self.assertEqual(data['summary'][0]['sheets'],1)
        self.assertEqual(data['summary'][0]['percent'],100)
        self.decision(c,'revised','Иная формулировка.',1)
        data=self.client.get(f'/api/round-table/{c}/').json()
        self.assertEqual(data['cases'],[])
        self.assertEqual(data['stale_count'],1)

    def test_original_edit_requires_reconfirmation(self):
        c=self.create_cycle();self.decision(c);self.annotate(c)
        self.source.facts+=' Дополнение.';self.source.save()
        data=self.client.get(f'/api/round-table/{c}/').json()
        self.assertEqual(data['cases'],[])
        self.assertTrue(next(x for x in data['sources'] if x['key']==f'stage:{self.source.pk}')['source_changed'])
        self.assertEqual(self.annotate(c).status_code,409)

    def test_foreign_sources_and_cards_not_accessible(self):
        c=self.create_cycle()
        other=AuditAssessment.objects.create(audit_sheet=self.sheets[1],stage=self.stage,facts='Other')
        self.assertEqual(self.client.get(self.path(c,pk=other.pk)).status_code,404)
        self.assertEqual(self.client.get(self.path(c,kind='invalid')).status_code,404)
        self.decision(c)
        self.assertEqual(self.annotate(c).status_code,201)
        c2=self.create_cycle();self.decision(c2)
        response=self.client.patch(self.path(c2)+'observations/',{'id':TextObservation.objects.get().pk,'status':'excluded','revision':1},content_type='application/json')
        self.assertEqual(response.status_code,404)

    def test_finish_requires_all_texts_and_locks_mutations(self):
        c=self.create_cycle()
        close=lambda closed,revision:self.client.post(f'/api/round-table/{c}/',{'closed':closed,'revision':revision},content_type='application/json')
        self.assertEqual(close(True,0).status_code,400)
        self.decision(c)
        final=FinalMarkCrew.objects.get(audit_sheet=self.sheets[0])
        response=self.client.put(self.path(c,'final',final.pk),{'decision':'confirmed','agreed_text':'','note':'','revision':0,'source_digest':digest(final.general_notes)},content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(close(True,0).status_code,200)
        self.assertEqual(self.decision(c,revision=1).status_code,409)
        self.assertEqual(self.annotate(c).status_code,409)
        self.assertEqual(close(False,1).status_code,200)
        self.assertEqual(self.annotate(c).status_code,201)

    def test_legacy_card_visible_and_can_be_copied_without_editing_it(self):
        legacy=TextObservation.objects.create(audit_sheet=self.sheets[0],assessment=self.source,
            source_snapshot=self.source.facts,quote='Экипаж изучил погоду.',nature='practice',evidence='fact',
            created_by=self.coordinator,updated_by=self.coordinator)
        legacy.topics.add(self.topic)
        c=self.create_cycle();self.decision(c)
        self.assertEqual(self.client.get(self.path(c)).json()['legacy'][0]['id'],legacy.pk)
        self.annotate(c)
        legacy.refresh_from_db()
        self.assertIsNone(legacy.round_table_review_id)
        self.assertEqual(TextObservation.objects.count(),2)

    def test_csrf_and_portal_topic_creation(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.coordinator)
        self.assertEqual(client.post('/api/round-table/',{},content_type='application/json').status_code,403)
        response=self.client.post('/api/round-table/topics/',{'name':'Новая подтема','parent':self.topic.pk},content_type='application/json')
        self.assertEqual(response.status_code,201,response.content)

    def test_topic_denominator_is_cycle_and_multiple_fragments_count_once(self):
        response=self.client.post('/api/round-table/',{'name':'Две проверки','assignments':[str(s.portal_assignment.pk) for s in self.sheets[:2]]},content_type='application/json')
        c=response.json()['id'];self.decision(c);self.annotate(c)
        response=self.client.post(self.path(c)+'observations/',{'quote':'КВС проявлял суету.',
            'topics':[self.topic.pk],'nature':'difficulty','evidence':'opinion','note':'','revision':1},content_type='application/json')
        self.assertEqual(response.status_code,201)
        summary=self.client.get(f'/api/round-table/{c}/').json()['summary'][0]
        self.assertEqual((summary['percent'],summary['sheets'],summary['practice'],summary['difficulty']),(50,1,1,1))

    def test_closed_cycle_keeps_approved_summary_after_source_changes(self):
        c=self.create_cycle();self.decision(c);self.annotate(c)
        final=FinalMarkCrew.objects.get(audit_sheet=self.sheets[0])
        self.client.put(self.path(c,'final',final.pk),{'decision':'confirmed','agreed_text':'','note':'','revision':0,'source_digest':digest(final.general_notes)},content_type='application/json')
        self.client.post(f'/api/round-table/{c}/',{'closed':True,'revision':0},content_type='application/json')
        self.source.facts+=' Позднейшее уточнение.';self.source.save()
        data=self.client.get(f'/api/round-table/{c}/').json()
        self.assertTrue(data['cycle']['closed'])
        self.assertEqual(len(data['cases']),1)
        self.assertTrue(any(s['source_changed'] for s in data['sources']))
