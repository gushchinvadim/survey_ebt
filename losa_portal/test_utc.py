from django.test import TestCase, override_settings
from django.test.runner import DiscoverRunner
from unittest.mock import patch
from datetime import datetime,timezone,date
from losa_portal.access import program_today,can_start
from losa_portal import test_round_table as fixture
class UTCTests(TestCase):
    @classmethod
    def setUpTestData(cls):fixture.RoundTableTests.setUpTestData.__func__(cls)
    @override_settings(TIME_ZONE='Pacific/Auckland',LOSA_TIME_ZONE='Europe/Moscow')
    def test_midnight_utc_controls_start_despite_local_date(self):
        assignment=self.sheets[0].portal_assignment
        assignment.status='scheduled';assignment.date=date(2026,11,9)
        for instant,expected in [('2026-11-08T23:59:59+00:00',False),('2026-11-09T00:00:00+00:00',True)]:
            with patch('django.utils.timezone.now',return_value=datetime.fromisoformat(instant)):
                self.assertEqual(program_today(),date(2026,11,9) if expected else date(2026,11,8))
                self.assertEqual(can_start(assignment,self.auditor_user),expected)
