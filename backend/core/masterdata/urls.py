from django.urls import path
from core.masterdata import views

urlpatterns = [
    path("", views.list_master_data),
    path("<str:entity>/create/", views.create_master_data),
    path("<str:entity>/<int:object_id>/active/", views.set_active),
]
