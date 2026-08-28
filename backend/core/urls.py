from django.urls import include, path
from core.views import health

urlpatterns = [
    path("health/", health),
    path("accounts/", include("core.accounts.urls")),
    path("doctors/", include("core.doctors.urls")),
    path("master-data/", include("core.masterdata.urls")),
    path("records/", include("core.records.urls")),
    path("approvals/", include("core.approvals.urls")),
    path("chatbot/", include("core.chatbot.urls")),
]
