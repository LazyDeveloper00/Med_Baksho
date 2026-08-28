from django.urls import path
from core.doctors import views

urlpatterns = [
    path("availability/", views.availability_list),
    path("availability/mine/", views.my_availability_list),
    path("availability/create/", views.availability_create),
    path("availability/<int:availability_id>/update/", views.availability_update),
    path("availability/<int:availability_id>/deactivate/", views.availability_deactivate),
]
