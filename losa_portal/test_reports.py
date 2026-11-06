from django.test import TestCase
from . import test_round_table as rt
from .models import CycleReport, RoundTableCycle
from losa.models import FinalMarkCrew
from .text_analysis import digest


class ReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        rt.RoundTableTests.setUpTestData.__func__(cls)

    setUp = rt.RoundTableTests.setUp
    create_cycle = rt.RoundTableTests.create_cycle
    path = rt.RoundTableTests.path
    decision = rt.RoundTableTests.decision
    annotate = rt.RoundTableTests.annotate

    def publish(self, c):
        return self.client.post(f'/api/round-table/{c}/reports/', {
            'revision': 1, 'summary': 'Краткие итоги', 'conclusions': 'Подтвержденные выводы',
            'limitations': 'Небольшая выборка', 'decisions': 'Мероприятия не назначены.',
            'anonymized': True}, content_type='application/json')

    def closed_cycle(self):
        c = self.create_cycle()
        self.decision(c); self.annotate(c)
        final = FinalMarkCrew.objects.get(audit_sheet=self.sheets[0])
        self.client.put(self.path(c, 'final', final.pk), {'decision': 'confirmed', 'agreed_text': '',
            'note': '', 'revision': 0, 'source_digest': digest(final.general_notes)}, content_type='application/json')
        response = self.client.post(f'/api/round-table/{c}/', {'closed': True, 'revision': 0}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        return c

    def test_publication_requires_closed_cycle_and_permissions(self):
        c = self.create_cycle()
        self.assertEqual(self.publish(c).status_code, 409)
        self.client.force_login(self.auditor_user)
        self.assertEqual(self.publish(c).status_code, 403)
        self.assertEqual(self.client.get(f'/api/round-table/{c}/reports/').status_code, 403)

    def test_snapshot_versions_and_pdf_access(self):
        c = self.closed_cycle()
        response = self.publish(c)
        self.assertEqual(response.status_code, 201, response.content)
        report = CycleReport.objects.get()
        self.assertEqual(report.payload['topics'][0]['percent'], 100)
        self.assertNotIn('cases', report.payload)
        original = report.payload
        self.source.facts = 'Позднейшая правка'; self.source.save()
        self.topic.name = 'Новое имя темы'; self.topic.save()
        report.refresh_from_db()
        self.assertEqual(report.payload, original)
        for kind in ['results', 'decisions']:
            path = f'/api/round-table/{c}/reports/{report.pk}/{kind}/'
            pdf = self.client.get(path)
            self.assertEqual(pdf.status_code, 200)
            self.assertTrue(pdf.content.startswith(b'%PDF-'))
            self.client.force_login(self.auditor_user)
            self.assertEqual(self.client.get(path).status_code, 403)
            self.client.force_login(self.coordinator)
        self.assertEqual(self.publish(c).status_code, 201)
        self.assertEqual(list(CycleReport.objects.values_list('version', flat=True)), [2, 1])
        RoundTableCycle.objects.filter(pk=c).update(closed=False)
        self.assertEqual(self.publish(c).status_code, 409)
        self.assertEqual(self.client.get(f'/api/round-table/{c}/reports/{report.pk}/results/').status_code, 200)

    def test_empty_fields_csrf_and_anonymization_are_rejected(self):
        from django.test import Client
        c = self.closed_cycle()
        path = f'/api/round-table/{c}/reports/'
        self.assertEqual(self.client.post(path, {}, content_type='application/json').status_code, 400)
        data = dict(revision=1, summary='Итоги', conclusions='Выводы', limitations='Ограничения',
                    decisions='Решения', anonymized=False)
        self.assertEqual(self.client.post(path, data, content_type='application/json').status_code, 400)
        data['anonymized'] = True
        data['revision'] = 0
        self.assertEqual(self.client.post(path, data, content_type='application/json').status_code, 409)
        guarded = Client(enforce_csrf_checks=True)
        guarded.force_login(self.coordinator)
        self.assertEqual(guarded.post(path, data, content_type='application/json').status_code, 403)
        self.assertFalse(CycleReport.objects.exists())


from django.test import SimpleTestCase
from .pdf_charts import coverage, percentage, leading_rows
from .reports import render_pdf


class ChartTests(SimpleTestCase):
    def test_coverage_uses_sheets_not_event_count_and_handles_empty_denominator(self):
        row = {'name': 'Угроза', 'events': 12, 'sheets': 2}
        self.assertEqual(coverage(row['sheets'], 8), 25)
        self.assertEqual(percentage(row['sheets'], 8), '25,0%')
        self.assertEqual(percentage(0, 8), '0,0%')
        self.assertIsNone(coverage(0, 0))
        self.assertEqual(percentage(0, 0), 'н/д')
        rows = [{'name': str(i), 'sheets': i} for i in range(12)]
        selected = leading_rows(rows)
        self.assertEqual(len(selected), 8)
        self.assertEqual(selected[0]['sheets'], 11)
        self.assertEqual(len(rows), 12)

    def test_empty_and_long_labels_render_without_losing_categories(self):
        payload = dict(name='Тест', version=1, generated='2026-11-02', period=[], sheets=0,
                       texts=0, cards=0, summary='Нет данных', limitations='Нет выборки',
                       conclusions='Выводов нет', decisions='Решений нет', topics=[], threats=[], errors=[])
        self.assertTrue(render_pdf(payload, 'results').startswith(b'%PDF-'))
        payload['sheets'] = 10
        payload['threats'] = [{'name': ('Очень длинное название типа угрозы ' * 8) + str(i),
                               'events': 2, 'sheets': 1} for i in range(12)]
        self.assertTrue(render_pdf(payload, 'results').startswith(b'%PDF-'))
