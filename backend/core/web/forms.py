"""Django Form classes for the browser frontend.

Forms handle HTML-level validation only. All persistence flows through the
existing backend classes (Factory, Builder, Facade, Service) from the views.
"""

from datetime import date

from django import forms

from core.models import Disease, MedicineType

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]


class DateInput(forms.DateInput):
    input_type = "date"


class TimeInput(forms.TimeInput):
    input_type = "time"


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput, strip=False)


class _PasswordPairMixin(forms.Form):
    password = forms.CharField(min_length=6, widget=forms.PasswordInput, strip=False)
    confirm_password = forms.CharField(widget=forms.PasswordInput, strip=False)

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm = cleaned.get("confirm_password")
        if password and confirm and password != confirm:
            self.add_error("confirm_password", "The two passwords do not match.")
        return cleaned


class PatientRegistrationForm(_PasswordPairMixin):
    full_name = forms.CharField(max_length=255)
    email = forms.EmailField()
    phone = forms.CharField(max_length=50, required=False)
    date_of_birth = forms.DateField(required=False, widget=DateInput)
    blood_group = forms.ChoiceField(
        choices=[("", "Not specified")] + [(g, g) for g in BLOOD_GROUPS],
        required=False,
    )
    address = forms.CharField(widget=forms.Textarea, required=False)

    field_order = [
        "full_name",
        "email",
        "phone",
        "password",
        "confirm_password",
        "date_of_birth",
        "blood_group",
        "address",
    ]


class DoctorRegistrationForm(_PasswordPairMixin):
    full_name = forms.CharField(max_length=255)
    email = forms.EmailField()
    phone = forms.CharField(max_length=50, required=False)
    licence_number = forms.CharField(max_length=255)
    degree = forms.CharField(max_length=255, required=False)
    field_of_expertise = forms.CharField(max_length=255, required=False)
    workplace = forms.CharField(max_length=255, required=False)

    field_order = [
        "full_name",
        "email",
        "phone",
        "password",
        "confirm_password",
        "licence_number",
        "degree",
        "field_of_expertise",
        "workplace",
    ]


class PatientProfileForm(forms.Form):
    full_name = forms.CharField(max_length=255)
    phone = forms.CharField(max_length=50, required=False)
    date_of_birth = forms.DateField(required=False, widget=DateInput)
    blood_group = forms.ChoiceField(
        choices=[("", "Not specified")] + [(g, g) for g in BLOOD_GROUPS],
        required=False,
    )
    address = forms.CharField(widget=forms.Textarea, required=False)


class DoctorProfileForm(forms.Form):
    full_name = forms.CharField(max_length=255)
    phone = forms.CharField(max_length=50, required=False)
    degree = forms.CharField(max_length=255, required=False)
    field_of_expertise = forms.CharField(max_length=255, required=False)
    workplace = forms.CharField(max_length=255, required=False)


class AdminProfileForm(forms.Form):
    full_name = forms.CharField(max_length=255)
    phone = forms.CharField(max_length=50, required=False)


class DiseaseRecordForm(forms.Form):
    disease_id = forms.ChoiceField(choices=[])
    diagnosed_date = forms.DateField(required=False, widget=DateInput)
    current_status = forms.ChoiceField(
        choices=[
            ("Active", "Active"),
            ("Recovered", "Recovered"),
            ("Chronic", "Chronic"),
            ("Under Treatment", "Under Treatment"),
        ],
        initial="Active",
    )
    custom_disease_name = forms.CharField(max_length=255, required=False)
    notes = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        diseases = Disease.objects.filter(is_active=True).order_by("disease_name")
        self._disease_names = {str(d.disease_id): d.disease_name for d in diseases}
        self.fields["disease_id"].choices = [("", "Select a disease")] + [
            (str(d.disease_id), d.disease_name) for d in diseases
        ]

    def clean(self):
        cleaned = super().clean()
        disease_id = cleaned.get("disease_id")
        name = self._disease_names.get(str(disease_id), "")
        if name.strip().lower() == "other" and not (cleaned.get("custom_disease_name") or "").strip():
            self.add_error(
                "custom_disease_name",
                "A custom disease name is required when 'Other' is selected.",
            )
        return cleaned


class MedicineSubmissionForm(forms.Form):
    proposed_medicine_name = forms.CharField(max_length=255)
    med_brand_name = forms.CharField(max_length=255, required=False)
    proposed_active_ingredient = forms.CharField(max_length=255, required=False)


class AvailabilityForm(forms.Form):
    available_date = forms.DateField(widget=DateInput)
    start_time = forms.TimeField(widget=TimeInput)
    end_time = forms.TimeField(widget=TimeInput)
    visiting_fee = forms.DecimalField(min_value=0, max_digits=10, decimal_places=2)
    is_active = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, allow_past=False, **kwargs):
        self.allow_past = allow_past
        super().__init__(*args, **kwargs)

    def clean_available_date(self):
        value = self.cleaned_data["available_date"]
        if not self.allow_past and value < date.today():
            raise forms.ValidationError("The date cannot be in the past.")
        return value

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end and start >= end:
            self.add_error("end_time", "End time must be later than start time.")
        return cleaned


class ChatbotForm(forms.Form):
    question = forms.CharField(
        max_length=500,
        widget=forms.Textarea,
        error_messages={"max_length": "Question cannot exceed 500 characters."},
    )


class MedicineApprovalForm(forms.Form):
    med_type_id = forms.ChoiceField(choices=[])
    brand_id = forms.CharField(required=False)
    brand_name = forms.CharField(max_length=255, required=False)
    comments = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["med_type_id"].choices = [("", "Select a type")] + [
            (str(t.med_type_id), t.med_type_name)
            for t in MedicineType.objects.order_by("med_type_name")
        ]
