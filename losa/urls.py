# losa/urls.py
from django.contrib import admin
from django.urls import path
from django.conf.urls.static import static
from losa import views
from django.conf import settings
from django.contrib.auth import views as auth_views

urlpatterns = [

    # path('', views.index_page, name='index'),
    # path('login_form', views.login_form, name='login_form'),
    # path('current_flight_data', views.current_flight_data, name='current_flight_data'),
    # path('threatment_control', views.threatment_control, name='threatment_control'),
    # path('mistake_control', views.mistake_control, name='mistake_control'),

    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)