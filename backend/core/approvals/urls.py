from django.urls import path
from core.approvals import views

urlpatterns = [
    path("users/", views.users),
    path("users/<int:user_id>/status/", views.set_user_status),
    path("doctors/pending/", views.pending_doctors),
    path("doctors/<int:doctor_id>/approve/", views.approve_doctor),
    path("doctors/<int:doctor_id>/reject/", views.reject_doctor),
    path("medicines/pending/", views.pending_medicines),
    path("medicines/<int:submission_id>/approve/", views.approve_medicine),
    path("medicines/<int:submission_id>/reject/", views.reject_medicine),
    path("notifications/", views.notifications),
    path("activity/", views.activity),
]
