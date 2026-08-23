from django.conf import settings

from core.chatbot.strategies import (
    AIProviderStrategy,
    HuggingFaceStrategy,
    OpenRouterStrategy,
)
from core.models import Patient, Prescription


class ChatbotService:
    def __init__(self, provider: AIProviderStrategy):
        self.provider = provider

    def set_provider(self, provider: AIProviderStrategy) -> None:
        self.provider = provider

    def answer_question(self, patient: Patient, question: str) -> str:
        return self.provider.generate_response(question, self._build_patient_context(patient))

    def _build_patient_context(self, patient: Patient) -> str:
        diseases = patient.disease_records.select_related("disease").all()
        prescriptions = Prescription.objects.filter(
            patient_disease__patient=patient
        ).select_related("patient_disease__disease", "facility").order_by("-prescription_date")[:20]

        lines = [f"Patient: {patient.user.full_name}"]
        lines.append("Disease records:")
        if diseases:
            for item in diseases:
                lines.append(
                    f"- {item.disease.disease_name}; status={item.current_status}; "
                    f"diagnosed={item.diagnosed_date or 'unknown'}; notes={item.notes or 'none'}"
                )
        else:
            lines.append("- None")

        lines.append("Recent prescriptions:")
        if prescriptions:
            for item in prescriptions:
                facility = item.facility.facility_name if item.facility else item.custom_facility_name
                lines.append(
                    f"- {item.prescription_date}: disease={item.patient_disease.disease.disease_name}; "
                    f"doctor={item.doctor_name}; facility={facility}; advice={item.advice or 'none'}"
                )
        else:
            lines.append("- None")
        return "\n".join(lines)


def build_chatbot_service() -> ChatbotService:
    if settings.AI_PROVIDER == "huggingface":
        strategy = HuggingFaceStrategy(
            settings.HUGGINGFACE_API_KEY,
            settings.HUGGINGFACE_MODEL,
            settings.HUGGINGFACE_API_URL,
        )
    else:
        strategy = OpenRouterStrategy(
            settings.OPENROUTER_API_KEY,
            settings.OPENROUTER_MODEL,
        )
    return ChatbotService(strategy)
