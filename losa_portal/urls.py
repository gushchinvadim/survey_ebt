from django.urls import path
from . import views
from .analytics import analytics_view
from . import demography, completion

app_name = "losa_portal"

urlpatterns = [
    path("analytics/", analytics_view, name="analytics"),
    path("assignments/<uuid:pk>/completion/preview/", completion.preview_completion, name="completion-preview"),
    path("assignments/<uuid:pk>/complete/", completion.complete_assignment, name="assignment-complete"),
    path("assignments/<uuid:pk>/reopen/", completion.reopen_assignment, name="assignment-reopen"),
    path(
        "assignments/<uuid:pk>/demography/open/",
        demography.open_demography,
        name="demography-open",
    ),
    path(
        "assignments/<uuid:pk>/demography/",
        demography.save_demography,
        name="demography-save",
    ),
    path("auth/csrf/", views.csrf_view, name="csrf"),
    path("auth/login/", views.login_view, name="login"),
    path("auth/me/", views.me_view, name="me"),
    path("auth/logout/", views.logout_view, name="logout"),
    path("planning/catalog/", views.catalog_view, name="catalog"),
    path("assignments/", views.assignments_view, name="assignments"),
    path("assignments/<uuid:pk>/entry/", views.assignment_entry_view, name="entry"),
]
