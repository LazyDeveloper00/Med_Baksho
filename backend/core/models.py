from django.db import models
from django.utils import timezone


class UnmanagedModel(models.Model):
    class Meta:
        abstract = True
        managed = False


class Client(UnmanagedModel):
    user_id = models.AutoField(primary_key=True, db_column="user_id")
    full_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, unique=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    password_hash = models.CharField(max_length=255)
    account_status = models.CharField(max_length=50, default="Active")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta(UnmanagedModel.Meta):
        db_table = "client"


class Admin(UnmanagedModel):
    a_id = models.AutoField(primary_key=True, db_column="a_id")
    user = models.OneToOneField(
        Client,
        db_column="user_id",
        on_delete=models.CASCADE,
        related_name="admin_role",
    )

    class Meta(UnmanagedModel.Meta):
        db_table = "admin"


class Patient(UnmanagedModel):
    p_id = models.AutoField(primary_key=True, db_column="p_id")
    user = models.OneToOneField(
        Client,
        db_column="user_id",
        on_delete=models.CASCADE,
        related_name="patient_role",
    )
    date_of_birth = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=10, null=True, blank=True)
    address = models.TextField(null=True, blank=True)

    class Meta(UnmanagedModel.Meta):
        db_table = "patient"


class Doctor(UnmanagedModel):
    d_id = models.AutoField(primary_key=True, db_column="d_id")
    user = models.OneToOneField(
        Client,
        db_column="user_id",
        on_delete=models.CASCADE,
        related_name="doctor_role",
    )
    licence_number = models.CharField(max_length=255, unique=True)
    degree = models.CharField(max_length=255, null=True, blank=True)
    field_of_expertise = models.CharField(max_length=255, null=True, blank=True)
    workplace = models.CharField(max_length=255, null=True, blank=True)
    verification_status = models.CharField(max_length=50, default="Pending")
    verified_by_admin = models.ForeignKey(
        Admin,
        db_column="verified_by_admin_id",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_doctors",
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta(UnmanagedModel.Meta):
        db_table = "doctor"


class DoctorAvailability(UnmanagedModel):
    availability_id = models.AutoField(primary_key=True, db_column="availability_id")
    doctor = models.ForeignKey(
        Doctor,
        db_column="doctor_id",
        on_delete=models.CASCADE,
        related_name="availability_entries",
    )
    available_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    visiting_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta(UnmanagedModel.Meta):
        db_table = "doctoravailability"


class Disease(UnmanagedModel):
    disease_id = models.AutoField(primary_key=True, db_column="disease_id")
    disease_name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta(UnmanagedModel.Meta):
        db_table = "disease"


class PatientDisease(UnmanagedModel):
    patient_disease_id = models.AutoField(primary_key=True, db_column="patient_disease_id")
    patient = models.ForeignKey(
        Patient,
        db_column="patient_id",
        on_delete=models.CASCADE,
        related_name="disease_records",
    )
    disease = models.ForeignKey(
        Disease,
        db_column="disease_id",
        on_delete=models.RESTRICT,
        related_name="patient_records",
    )
    diagnosed_date = models.DateField(null=True, blank=True)
    current_status = models.CharField(max_length=50, default="Active")
    custom_disease_name = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    class Meta(UnmanagedModel.Meta):
        db_table = "patientdisease"


class MedicalFacilityType(UnmanagedModel):
    facility_type_id = models.AutoField(primary_key=True, db_column="facility_type_id")
    facility_type_name = models.CharField(max_length=255, unique=True)

    class Meta(UnmanagedModel.Meta):
        db_table = "medicalfacilitytype"


class MedicalFacility(UnmanagedModel):
    facility_id = models.AutoField(primary_key=True, db_column="facility_id")
    facility_name = models.CharField(max_length=255)
    facility_type = models.ForeignKey(
        MedicalFacilityType,
        db_column="facility_type_id",
        on_delete=models.RESTRICT,
        related_name="facilities",
    )
    is_active = models.BooleanField(default=True)

    class Meta(UnmanagedModel.Meta):
        db_table = "medicalfacility"
        unique_together = (("facility_name", "facility_type"),)


class MedicineBrand(UnmanagedModel):
    brand_id = models.AutoField(primary_key=True, db_column="brand_id")
    brand_name = models.CharField(max_length=255, unique=True)

    class Meta(UnmanagedModel.Meta):
        db_table = "medicinebrand"


class MedicineType(UnmanagedModel):
    med_type_id = models.AutoField(primary_key=True, db_column="med_type_id")
    med_type_name = models.CharField(max_length=255, unique=True)

    class Meta(UnmanagedModel.Meta):
        db_table = "medicinetype"


class Medicine(UnmanagedModel):
    medicine_id = models.AutoField(primary_key=True, db_column="medicine_id")
    medicine_name = models.CharField(max_length=255)
    main_active_ingredient = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    med_brand = models.ForeignKey(
        MedicineBrand,
        db_column="med_brand_id",
        on_delete=models.RESTRICT,
        related_name="medicines",
    )
    med_type = models.ForeignKey(
        MedicineType,
        db_column="med_type_id",
        on_delete=models.RESTRICT,
        related_name="medicines",
    )

    class Meta(UnmanagedModel.Meta):
        db_table = "medicine"
        unique_together = (("medicine_name", "med_brand", "med_type"),)


class TestCategory(UnmanagedModel):
    category_id = models.AutoField(primary_key=True, db_column="category_id")
    category_name = models.CharField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta(UnmanagedModel.Meta):
        db_table = "testcategory"


class MedicalTest(UnmanagedModel):
    test_id = models.AutoField(primary_key=True, db_column="test_id")
    category = models.ForeignKey(
        TestCategory,
        db_column="category_id",
        on_delete=models.RESTRICT,
        related_name="tests",
    )
    test_name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta(UnmanagedModel.Meta):
        db_table = "medicaltest"
        unique_together = (("category", "test_name"),)


class Prescription(UnmanagedModel):
    prescription_id = models.AutoField(primary_key=True, db_column="prescription_id")
    patient_disease = models.ForeignKey(
        PatientDisease,
        db_column="patient_disease_id",
        on_delete=models.CASCADE,
        related_name="prescriptions",
    )
    facility = models.ForeignKey(
        MedicalFacility,
        db_column="facility_id",
        on_delete=models.RESTRICT,
        related_name="prescriptions",
        null=True,
        blank=True,
    )
    prescription_date = models.DateField()
    doctor_name = models.CharField(max_length=255)
    custom_facility_name = models.CharField(max_length=255, null=True, blank=True)
    illness_location = models.CharField(max_length=255, null=True, blank=True)
    advice = models.TextField(null=True, blank=True)
    additional_notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta(UnmanagedModel.Meta):
        db_table = "prescription"


class PrescriptionMedicine(UnmanagedModel):
    pk = models.CompositePrimaryKey("prescription_id", "medicine_id")
    prescription = models.ForeignKey(
        Prescription,
        db_column="prescription_id",
        on_delete=models.CASCADE,
        related_name="medicine_entries",
    )
    medicine = models.ForeignKey(
        Medicine,
        db_column="medicine_id",
        on_delete=models.RESTRICT,
        related_name="prescription_entries",
    )
    dosage = models.CharField(max_length=255)
    times_per_day = models.PositiveIntegerField()
    duration_days = models.PositiveIntegerField()
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    course_completed = models.BooleanField(default=False)
    side_effects = models.TextField(null=True, blank=True)
    effectiveness = models.CharField(max_length=255, default="Unknown")

    class Meta(UnmanagedModel.Meta):
        db_table = "prescriptionmedicine"


class PrescriptionTest(UnmanagedModel):
    pk = models.CompositePrimaryKey("prescription_id", "test_id")
    prescription = models.ForeignKey(
        Prescription,
        db_column="prescription_id",
        on_delete=models.CASCADE,
        related_name="test_entries",
    )
    test = models.ForeignKey(
        MedicalTest,
        db_column="test_id",
        on_delete=models.RESTRICT,
        related_name="prescription_entries",
    )
    completion_status = models.CharField(max_length=50, default="Recommended")
    test_date = models.DateField(null=True, blank=True)
    diagnostic_center_name = models.CharField(max_length=255, null=True, blank=True)
    result_summary = models.TextField(null=True, blank=True)
    custom_test_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta(UnmanagedModel.Meta):
        db_table = "prescriptiontest"


class PrescriptionImage(UnmanagedModel):
    image_id = models.AutoField(primary_key=True, db_column="image_id")
    prescription = models.ForeignKey(
        Prescription,
        db_column="prescription_id",
        on_delete=models.CASCADE,
        related_name="images",
    )
    file_path = models.CharField(max_length=500)
    file_size_kb = models.PositiveIntegerField(null=True, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta(UnmanagedModel.Meta):
        db_table = "prescriptionimage"
        unique_together = (("prescription", "file_path"),)


class MedicineSubmission(UnmanagedModel):
    submission_id = models.AutoField(primary_key=True, db_column="submission_id")
    patient = models.ForeignKey(
        Patient,
        db_column="patient_id",
        on_delete=models.CASCADE,
        related_name="medicine_submissions",
    )
    reviewed_by_admin = models.ForeignKey(
        Admin,
        db_column="reviewed_by_admin_id",
        on_delete=models.SET_NULL,
        related_name="reviewed_medicine_submissions",
        null=True,
        blank=True,
    )
    approved_medicine = models.ForeignKey(
        Medicine,
        db_column="approved_medicine_id",
        on_delete=models.SET_NULL,
        related_name="source_submissions",
        null=True,
        blank=True,
    )
    proposed_medicine_name = models.CharField(max_length=255)
    med_brand_name = models.CharField(max_length=255, null=True, blank=True)
    proposed_active_ingredient = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=50, default="Pending")
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comments = models.TextField(null=True, blank=True)

    class Meta(UnmanagedModel.Meta):
        db_table = "medicinesubmission"
