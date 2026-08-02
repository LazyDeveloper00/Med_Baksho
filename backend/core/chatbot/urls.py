from django.urls import path
from core.chatbot import views

urlpatterns = [path("ask/", views.ask)]
