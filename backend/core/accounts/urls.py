from django.urls import path
from core.accounts import views

urlpatterns = [
    path("register/patient/", views.register_patient),
    path("register/doctor/", views.register_doctor),
    path("login/", views.login),
    path("logout/", views.logout),
    path("profile/", views.profile),
    path("profile/update/", views.update_profile),
]
