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
        return self.provider.generate_response(
            question,
            self._build_patient_context(patient),
        )

    def _build_patient_context(self, patient: Patient) -> str:
        diseases = patient.disease_records.select_related("disease").all()

        prescriptions = (
            Prescription.objects.filter(patient_disease__patient=patient)
            .select_related(
                "patient_disease__disease",
                "facility",
            )
            .prefetch_related(
                "medicine_entries__medicine",
                "test_entries__test",
            )
            .order_by("-prescription_date")[:20]
        )

        lines = [f"Patient: {patient.user.full_name}"]

        lines.append("Disease records:")
        if diseases:
            for item in diseases:
                lines.append(
                    f"- Disease: {item.disease.disease_name}; "
                    f"status={item.current_status}; "
                    f"diagnosed={item.diagnosed_date or 'unknown'}; "
                    f"notes={item.notes or 'none'}"
                )
        else:
            lines.append("- None")

        lines.append("Recent prescriptions:")

        if prescriptions:
            for item in prescriptions:
                facility = (
                    item.facility.facility_name
                    if item.facility
                    else item.custom_facility_name
                )

                lines.append(
                    f"- Prescription {item.prescription_id}: "
                    f"date={item.prescription_date}; "
                    f"disease={item.patient_disease.disease.disease_name}; "
                    f"doctor={item.doctor_name}; "
                    f"facility={facility or 'unknown'}; "
                    f"illness_location={item.illness_location or 'none'}; "
                    f"advice={item.advice or 'none'}; "
                    f"additional_notes={item.additional_notes or 'none'}"
                )

                medicines = item.medicine_entries.all()

                if medicines:
                    lines.append("  Medicines:")
                    for entry in medicines:
                        lines.append(
                            f"  - {entry.medicine.medicine_name}; "
                            f"active_ingredient="
                            f"{entry.medicine.main_active_ingredient or 'unknown'}; "
                            f"dosage={entry.dosage}; "
                            f"times_per_day={entry.times_per_day}; "
                            f"duration_days={entry.duration_days}; "
                            f"start_date={entry.start_date or 'unknown'}; "
                            f"end_date={entry.end_date or 'unknown'}; "
                            f"course_completed={entry.course_completed}; "
                            f"side_effects={entry.side_effects or 'none'}; "
                            f"effectiveness={entry.effectiveness}"
                        )
                else:
                    lines.append("  Medicines: None")

                tests = item.test_entries.all()

                if tests:
                    lines.append("  Medical tests:")
                    for entry in tests:
                        test_name = (
                            entry.custom_test_name
                            or entry.test.test_name
                        )

                        lines.append(
                            f"  - {test_name}; "
                            f"completion_status={entry.completion_status}; "
                            f"test_date={entry.test_date or 'unknown'}; "
                            f"diagnostic_center="
                            f"{entry.diagnostic_center_name or 'unknown'}; "
                            f"result_summary={entry.result_summary or 'none'}"
                        )
                else:
                    lines.append("  Medical tests: None")

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