from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings

from losa.models import Aircraft, Airport, Auditor, Company, Location, Pilot
from .access import AUDITOR_GROUP, COORDINATOR_GROUP, program_today
from .models import AuditAssignment, Flight, PortalProfile


@override_settings(LOSA_TIME_ZONE="Europe/Moscow")
class PortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.coordinator = User.objects.create_user(
            "coordinator", password="TestOnly2026!"
        )
        cls.auditor_user = User.objects.create_user("auditor", password="TestOnly2026!")
        cls.other_user = User.objects.create_user("other", password="TestOnly2026!")
        cls.no_role = User.objects.create_user("no-role", password="TestOnly2026!")
        coord_group = Group.objects.create(name=COORDINATOR_GROUP)
        audit_group = Group.objects.create(name=AUDITOR_GROUP)
        cls.coordinator.groups.add(coord_group)
        cls.auditor_user.groups.add(audit_group)
        cls.other_user.groups.add(audit_group)
        cls.auditor = Auditor.objects.create(auditor_code=1, name="First Auditor")
        cls.other_auditor = Auditor.objects.create(auditor_code=2, name="Other Auditor")
        PortalProfile.objects.create(user=cls.auditor_user, auditor=cls.auditor)
        PortalProfile.objects.create(user=cls.other_user, auditor=cls.other_auditor)
        location = Location.objects.create(location_code="L", location_name="Base")
        company = Company.objects.create(company_code="C", company_name="Company")
        cls.captain = Pilot.objects.create(
            pilot_id=10,
            company=company,
            location=location,
            position="CAPT",
            experience=10,
            type_experience=5,
        )
        cls.officer = Pilot.objects.create(
            pilot_id=20,
            company=company,
            location=location,
            position="FO",
            experience=4,
            type_experience=2,
        )
        airport = Airport.objects.create(airport_code="AAA", airport_name="Airport")
        aircraft = Aircraft.objects.create(aircraft_type="Type")
        cls.flight = Flight.objects.create(
            number="F101",
            departure=airport,
            arrival=airport,
            time="10:00",
            aircraft=aircraft,
        )
        cls.assignment = AuditAssignment.objects.create(
            date=program_today(),
            flight=cls.flight,
            captain=cls.captain,
            first_officer=cls.officer,
            auditor=cls.auditor,
            created_by=cls.coordinator,
        )

    def login_client(self, username="auditor"):
        client = Client(enforce_csrf_checks=True)
        client.get("/api/auth/csrf/")
        token = client.cookies["csrftoken"].value
        result = client.post(
            "/api/auth/login/",
            {"username": username, "password": "TestOnly2026!"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(result.status_code, 200, result.content)
        return client

    def test_csrf_required_for_login(self):
        client = Client(enforce_csrf_checks=True)
        result = client.post(
            "/api/auth/login/",
            {"username": "auditor", "password": "TestOnly2026!"},
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 403)

    def test_login_me_logout(self):
        client = self.login_client()
        self.assertEqual(
            client.get("/api/auth/me/").json()["auditor_id"], self.auditor.pk
        )
        token = client.cookies["csrftoken"].value
        self.assertEqual(
            client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=token).status_code, 200
        )
        self.assertEqual(client.get("/api/auth/me/").status_code, 401)

    def test_bad_password_and_roleless_login(self):
        for username, password, expected in [
            ("auditor", "wrong", 401),
            ("no-role", "TestOnly2026!", 403),
        ]:
            result = self.client.post(
                "/api/auth/login/",
                {"username": username, "password": password},
                content_type="application/json",
            )
            self.assertEqual(result.status_code, expected)

    def test_inactive_user_cannot_login(self):
        self.auditor_user.is_active = False
        self.auditor_user.save()
        result = self.client.post(
            "/api/auth/login/",
            {"username": "auditor", "password": "TestOnly2026!"},
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 401)

    def test_auditor_sees_only_own_and_cannot_create(self):
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get("/api/assignments/").json(), [])
        self.assertEqual(
            self.client.post(
                "/api/assignments/", {}, content_type="application/json"
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                f"/api/assignments/{self.assignment.pk}/entry/"
            ).status_code,
            404,
        )
        self.assertEqual(self.client.get("/api/planning/catalog/").json()["pilots"], [])

    def test_coordinator_does_not_implicitly_become_auditor(self):
        self.client.force_login(self.coordinator)
        self.assertEqual(
            self.client.get("/api/auth/me/").json()["roles"], ["coordinator"]
        )
        self.assertEqual(
            self.client.get(
                f"/api/assignments/{self.assignment.pk}/entry/"
            ).status_code,
            403,
        )

    def test_server_checks_date_and_status(self):
        self.client.force_login(self.auditor_user)
        url = f"/api/assignments/{self.assignment.pk}/entry/"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assignment.date = program_today() + timedelta(days=1)
        self.assignment.save()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assignment.date = program_today() - timedelta(days=1)
        self.assignment.save()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assignment.date = program_today()
        self.assignment.status = "completed"
        self.assignment.save()
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_coordinator_can_also_be_auditor(self):
        self.auditor_user.groups.add(Group.objects.get(name=COORDINATOR_GROUP))
        self.client.force_login(self.auditor_user)
        self.assertEqual(
            set(self.client.get("/api/auth/me/").json()["roles"]),
            {"coordinator", "auditor"},
        )
        self.assertEqual(
            self.client.get(
                f"/api/assignments/{self.assignment.pk}/entry/"
            ).status_code,
            200,
        )

    def test_assignment_create_duplicate_and_csrf(self):
        client = self.login_client("coordinator")
        data = {
            "date": str(program_today() + timedelta(days=1)),
            "flight": self.flight.pk,
            "captain": self.captain.pk,
            "first_officer": self.officer.pk,
            "auditor": self.auditor.pk,
        }
        self.assertEqual(
            client.post(
                "/api/assignments/", data, content_type="application/json"
            ).status_code,
            403,
        )
        token = client.cookies["csrftoken"].value
        result = client.post(
            "/api/assignments/",
            data,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(result.status_code, 201, result.content)
        result = client.post(
            "/api/assignments/",
            data,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertIn(result.status_code, [400, 409])

    def test_same_pilot_rejected(self):
        self.client.force_login(self.coordinator)
        data = {
            "date": str(program_today() + timedelta(days=2)),
            "flight": self.flight.pk,
            "captain": self.captain.pk,
            "first_officer": self.captain.pk,
            "auditor": self.auditor.pk,
        }
        self.assertEqual(
            self.client.post(
                "/api/assignments/", data, content_type="application/json"
            ).status_code,
            400,
        )

    def test_anonymous_cannot_read(self):
        self.assertEqual(self.client.get("/api/assignments/").status_code, 401)

    def test_new_crew_fields_and_delay_partial_updates(self):
        from losa.models import AuditSheet
        from losa.serializers import PilotSerializer, AuditSheetSerializer

        pilot = PilotSerializer(self.captain, data={"fmc_experience": 6}, partial=True)
        self.assertTrue(pilot.is_valid(), pilot.errors)
        pilot.save()
        sheet = AuditSheet.objects.create(
            audit_number="CREW-1",
            auditor=self.auditor,
            aircraft=self.flight.aircraft,
            captain=self.captain,
            first_officer=self.officer,
            departure=self.flight.departure,
            arrival=self.flight.arrival,
            working_together="1",
        )
        serializer = AuditSheetSerializer(
            sheet,
            data={
                "leg_number": "1 из 2",
                "pilot_flying": "1",
                "is_delay": True,
                "delay": 15,
            },
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        sheet.refresh_from_db()
        self.assertEqual(sheet.leg_number, "1 из 2")
        self.assertEqual(sheet.get_leg_number_display(), "1 из 2")
        serializer = AuditSheetSerializer(sheet, data={"is_delay": False}, partial=True)
        self.assertFalse(serializer.is_valid())
        serializer = AuditSheetSerializer(
            sheet, data={"is_delay": False, "delay": None}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertFalse(
            PilotSerializer(
                self.captain, data={"fmc_experience": -1}, partial=True
            ).is_valid()
        )

    def test_all_losa_serializers_construct(self):
        from losa import serializers

        for name in dir(serializers):
            cls = getattr(serializers, name)
            if (
                isinstance(cls, type)
                and name.endswith("Serializer")
                and hasattr(cls, "Meta")
            ):
                self.assertIn("id", cls().fields)

    def open_block(self):
        self.client.force_login(self.auditor_user)
        response = self.client.post(
            f"/api/assignments/{self.assignment.pk}/demography/open/"
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_demography_bootstrap_snapshots_and_repeat_open(self):
        from losa.models import AuditSheet

        data = self.open_block()
        self.assertEqual(data["form"]["captain_experience"], 10)
        self.assertEqual(data["form"]["first_officer_type_experience"], 2)
        self.assertTrue(data["audit_number"].startswith("LOSA-"))
        self.captain.experience = 20
        self.captain.save()
        again = self.open_block()
        self.assertEqual(again["form"]["captain_experience"], 10)
        self.assertEqual(AuditSheet.objects.count(), 1)

    def test_demography_save_route_and_experience_does_not_change_catalog(self):
        data = self.open_block()
        values = {**data["form"], "revision": data["revision"]}
        values.update(
            captain_experience=12,
            actual_arrival="Запасной аэродром",
            date="2026-10-18",
            working_together="2",
            is_delay=True,
            delay=35,
        )
        response = self.client.put(
            f"/api/assignments/{self.assignment.pk}/demography/",
            values,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["revision"], 1)
        self.captain.refresh_from_db()
        self.assertEqual(self.captain.experience, 10)
        self.assignment.refresh_from_db()
        self.assertEqual(
            self.assignment.audit_sheet.actual_arrival, "Запасной аэродром"
        )
        self.assertEqual(self.assignment.date, program_today())
        self.assertEqual(self.assignment.audit_sheet.date.isoformat(), "2026-10-18")

    def test_demography_conflicts_and_retry_are_safe(self):
        data = self.open_block()
        values = {**data["form"], "revision": 0, "captain_experience": 15}
        url = f"/api/assignments/{self.assignment.pk}/demography/"
        self.assertEqual(
            self.client.put(url, values, content_type="application/json").status_code,
            200,
        )
        retry = self.client.put(url, values, content_type="application/json")
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json()["revision"], 1)
        values["captain_experience"] = 16
        self.assertEqual(
            self.client.put(url, values, content_type="application/json").status_code,
            409,
        )

    def test_demography_cannot_change_assignment_or_other_sheet(self):
        data = self.open_block()
        url = f"/api/assignments/{self.assignment.pk}/demography/"
        values = {**data["form"], "revision": 0, "auditor": self.other_auditor.pk}
        self.assertEqual(
            self.client.put(url, values, content_type="application/json").status_code,
            400,
        )
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.post(url + "open/").status_code, 404)
        self.assertEqual(
            self.client.put(
                url, {**data["form"], "revision": 0}, content_type="application/json"
            ).status_code,
            404,
        )

    def test_demography_started_draft_can_resume_later(self):
        self.open_block()
        self.assignment.refresh_from_db()
        self.assignment.date = program_today() - timedelta(days=1)
        self.assignment.save()
        self.assertEqual(
            self.client.post(
                f"/api/assignments/{self.assignment.pk}/demography/open/"
            ).status_code,
            200,
        )
        self.assignment.status = "completed"
        self.assignment.save()
        self.assertEqual(
            self.client.post(
                f"/api/assignments/{self.assignment.pk}/demography/open/"
            ).status_code,
            403,
        )

    def test_demography_csrf_and_number_stability(self):
        client = self.login_client()
        url = f"/api/assignments/{self.assignment.pk}/demography/open/"
        self.assertEqual(client.post(url).status_code, 403)
        self.assertEqual(
            client.post(
                url, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value
            ).status_code,
            200,
        )
        number = self.assignment.number
        self.assignment.save()
        self.assertEqual(self.assignment.number, number)

    def test_demography_validation_and_delay_clear(self):
        data = self.open_block()
        values = {**data["form"], "revision": 0, "captain_type_experience": 50}
        url = f"/api/assignments/{self.assignment.pk}/demography/"
        self.assertEqual(
            self.client.put(url, values, content_type="application/json").status_code,
            400,
        )
        values = {**data["form"], "revision": 0, "is_delay": False, "delay": 35}
        result = self.client.put(url, values, content_type="application/json")
        self.assertEqual(result.status_code, 200, result.content)
        self.assertIsNone(result.json()["form"]["delay"])
