"""Browser (server-rendered) routes. The /api/ JSON routes stay unchanged."""

from django.urls import path

from core.web import views

urlpatterns = [
    # Public
    path("", views.home),
    path("doctors/availability/", views.doctor_availability),

    # Account
    path("login/", views.login_view),
    path("logout/", views.logout_view),
    path("register/patient/", views.register_patient),
    path("register/doctor/", views.register_doctor),
    path("profile/", views.profile_view),
    path("notifications/", views.notifications_view),

    # Patient
    path("patient/dashboard/", views.patient_dashboard),
    path("patient/diseases/", views.patient_diseases),
    path("patient/diseases/add/", views.patient_disease_add),
    path("patient/prescriptions/", views.patient_prescriptions),
    path("patient/prescriptions/add/", views.patient_prescription_add),
    path("patient/prescriptions/<int:prescription_id>/", views.patient_prescription_detail),
    path("patient/search/", views.patient_search),
    path("patient/medicine-submissions/", views.patient_medicine_submissions),
    path("patient/medicine-submissions/add/", views.patient_medicine_submission_add),
    path("patient/chatbot/", views.patient_chatbot),

    # Doctor
    path("doctor/dashboard/", views.doctor_dashboard),
    path("doctor/profile/", views.doctor_profile),
    path("doctor/availability/", views.doctor_availability_list),
    path("doctor/availability/add/", views.doctor_availability_add),
    path("doctor/availability/<int:availability_id>/edit/", views.doctor_availability_edit),

    # Administrator
    path("admin-panel/dashboard/", views.admin_dashboard),
    path("admin-panel/users/", views.admin_users),
    path("admin-panel/doctors/pending/", views.admin_pending_doctors),
    path("admin-panel/medicines/pending/", views.admin_pending_medicines),
    path("admin-panel/master-data/", views.admin_master_data),
    path("admin-panel/activity/", views.admin_activity),
]
