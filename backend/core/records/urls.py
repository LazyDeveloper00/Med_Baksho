from django.urls import path
from core.records import views

urlpatterns = [
    path("diseases/", views.disease_records),
    path("diseases/create/", views.disease_create),
    path("prescriptions/", views.prescription_list),
    path("prescriptions/create/", views.prescription_create),
    path("prescriptions/<int:prescription_id>/", views.prescription_detail),
    path("search/", views.prescription_search),
    path("medicine-submissions/create/", views.medicine_submission_create),
    path("medicine-submissions/", views.medicine_submission_list),
]
