from django.test import TestCase, Client
from django.test.runner import DiscoverRunner
from django.contrib.auth import get_user_model
from losa_portal import test_round_table as fixture
from losa_portal.models import Flight, PortalProfile
from losa.models import Pilot,Auditor,Airport,Aircraft,Company,Location
from losa_portal.access import roles_for

class PlanningCatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):fixture.RoundTableTests.setUpTestData.__func__(cls)
    setUp=fixture.RoundTableTests.setUp
    def post(self,kind,data):
        return self.client.post(f'/api/planning/references/{kind}/',data,content_type='application/json')
    def auditor_data(self,**kwargs):
        return {'auditor_code':800,'name':'Новый аудитор','username':'new_auditor','password':'T6!wQ9#zL2@rK7',**kwargs}
    def test_coordinator_without_admin_creates_login_usable_on_ipad(self):
        self.assertFalse(self.coordinator.is_staff)
        data=self.auditor_data();response=self.post('auditors',data)
        self.assertEqual(response.status_code,201,response.content)
        user=get_user_model().objects.get(username=data['username'])
        self.assertFalse(user.is_staff);self.assertFalse(user.is_superuser)
        self.assertEqual(roles_for(user),['auditor'])
        self.assertTrue(user.check_password(data['password']))
        self.assertEqual(PortalProfile.objects.get(user=user).auditor_id,response.json()['id'])
        self.assertNotIn('password',response.content.decode())
        catalog=self.client.get('/api/planning/catalog/').json()
        self.assertTrue(next(a for a in catalog['auditors'] if a['id']==response.json()['id'])['is_active'])
        client=Client();login=client.post('/api/auth/login/',{'username':data['username'],'password':data['password']},content_type='application/json')
        self.assertEqual(login.status_code,200,login.content)
        self.assertEqual(login.json()['auditor_id'],response.json()['id'])
    def test_auditor_validation_does_not_create_partial_records(self):
        before=(Auditor.objects.count(),get_user_model().objects.count())
        for changes in [{'password':'123'}, {'username':'bad name'}, {'is_superuser':True}]:
            self.assertEqual(self.post('auditors',self.auditor_data(**changes)).status_code,400)
            self.assertEqual((Auditor.objects.count(),get_user_model().objects.count()),before)
        self.assertEqual(self.post('auditors',self.auditor_data()).status_code,201)
        for changes in [{'username':'another'}, {'username':'NEW_AUDITOR','auditor_code':801}]:
            self.assertEqual(self.post('auditors',self.auditor_data(**changes)).status_code,400)
    def test_flight_and_pilot_creation_validation_and_catalog(self):
        Airport.objects.create(airport_code='NEW',airport_name='New airport')
        airports=list(Airport.objects.all()[:2]);self.assertEqual(len(airports),2)
        flight={'number':' NEW 123 ','departure':airports[0].pk,'arrival':airports[1].pk,'time':'13:20','aircraft':Aircraft.objects.first().pk}
        created=self.post('flights',flight);self.assertEqual(created.status_code,201,created.content)
        self.assertEqual(Flight.objects.get(pk=created.json()['id']).number,'NEW 123')
        self.assertEqual(self.post('flights',flight).status_code,400)
        self.assertEqual(self.post('flights',{**flight,'arrival':airports[0].pk}).status_code,400)
        pilot={'pilot_id':98765,'company':Company.objects.first().pk,'location':Location.objects.first().pk,'position':'FO','experience':10,'type_experience':4,'fmc_experience':None}
        result=self.post('pilots',pilot);self.assertEqual(result.status_code,201,result.content)
        self.assertEqual(self.post('pilots',pilot).status_code,400)
        self.assertEqual(self.post('pilots',{**pilot,'pilot_id':98766,'type_experience':11}).status_code,400)
        self.assertEqual(self.post('pilots',{**pilot,'pilot_id':98766,'company':99999}).status_code,400)
        catalog=self.client.get('/api/planning/catalog/').json()
        self.assertIn(result.json()['id'],[p['id'] for p in catalog['pilots']])
        self.assertIn(created.json()['id'],[p['id'] for p in catalog['flights']])
    def test_permissions_and_csrf(self):
        self.client.logout()
        self.assertEqual(self.post('auditors',self.auditor_data()).status_code,401)
        self.client.force_login(self.auditor_user)
        self.assertEqual(self.client.get('/api/planning/references/options/').status_code,403)
        for kind in ['flights','pilots','auditors']:
            self.assertEqual(self.post(kind,{}).status_code,403)
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.coordinator)
        self.assertEqual(secure.post('/api/planning/references/auditors/',self.auditor_data(),content_type='application/json').status_code,403)
    def test_created_records_can_be_assigned(self):
        self.assertEqual(self.post('auditors',self.auditor_data()).status_code,201)
        pilots=list(Pilot.objects.all()[:2]);flight=Flight.objects.first();auditor=Auditor.objects.get(auditor_code=800)
        response=self.client.post('/api/assignments/',{'date':'2026-11-09','flight':flight.pk,'captain':pilots[0].pk,'first_officer':pilots[1].pk,'auditor':auditor.pk},content_type='application/json')
        self.assertEqual(response.status_code,201,response.content)


    def test_new_airports_are_available_and_usable_for_new_flight(self):
        departure=self.post('airports',{'airport_code':' abc1 ','airport_name':'Новый вылет'})
        arrival=self.post('airports',{'airport_code':'XYZ2','airport_name':'Новый прилет'})
        self.assertEqual(departure.status_code,201,departure.content)
        self.assertEqual(arrival.status_code,201,arrival.content)
        self.assertEqual(Airport.objects.get(pk=departure.json()['id']).airport_code,'ABC1')
        options=self.client.get('/api/planning/references/options/').json()
        self.assertIn(departure.json()['id'],[a['id'] for a in options['airports']])
        result=self.post('flights',{'number':'N123','departure':departure.json()['id'],
            'arrival':arrival.json()['id'],'time':'14:30','aircraft':Aircraft.objects.first().pk})
        self.assertEqual(result.status_code,201,result.content)
        catalog=self.client.get('/api/planning/catalog/').json()
        flight=next(f for f in catalog['flights'] if f['id']==result.json()['id'])
        self.assertEqual((flight['departure'],flight['arrival']),('ABC1','XYZ2'))
    def test_airport_validation_and_permissions(self):
        self.assertEqual(self.post('airports',{'airport_code':'NEW','airport_name':'Новый'}).status_code,201)
        count=Airport.objects.count()
        for data in [{'airport_code':' new ','airport_name':'Дубль'},
                     {'airport_code':'','airport_name':'Нет кода'},
                     {'airport_code':'AA BB','airport_name':'Пробел'},
                     {'airport_code':'QQQ','airport_name':''}]:
            self.assertEqual(self.post('airports',data).status_code,400)
        self.assertEqual(Airport.objects.count(),count)
        self.client.force_login(self.auditor_user)
        self.assertEqual(self.post('airports',{'airport_code':'ZZZ','airport_name':'Запрет'}).status_code,403)
        self.assertEqual(Airport.objects.count(),count)
