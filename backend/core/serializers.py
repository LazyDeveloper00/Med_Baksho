from core.models import (
    Doctor,
    DoctorAvailability,
    MedicineSubmission,
    PatientDisease,
    Prescription,
)


def client_dict(client):
    return {
        "user_id": client.user_id,
        "full_name": client.full_name,
        "email": client.email,
        "phone": client.phone,
        "account_status": client.account_status,
        "created_at": client.created_at.isoformat() if client.created_at else None,
    }


def doctor_dict(doctor: Doctor):
    return {
        "d_id": doctor.d_id,
        "user": client_dict(doctor.user),
        "licence_number": doctor.licence_number,
        "degree": doctor.degree,
        "field_of_expertise": doctor.field_of_expertise,
        "workplace": doctor.workplace,
        "verification_status": doctor.verification_status,
        "verified_at": doctor.verified_at.isoformat() if doctor.verified_at else None,
    }


def availability_dict(item: DoctorAvailability):
    return {
        "availability_id": item.availability_id,
        "doctor_id": item.doctor_id,
        "doctor_name": item.doctor.user.full_name,
        "field_of_expertise": item.doctor.field_of_expertise,
        "workplace": item.doctor.workplace,
        "available_date": item.available_date.isoformat(),
        "start_time": item.start_time.isoformat(),
        "end_time": item.end_time.isoformat(),
        "visiting_fee": str(item.visiting_fee),
        "is_active": item.is_active,
    }


def patient_disease_dict(item: PatientDisease):
    return {
        "patient_disease_id": item.patient_disease_id,
        "disease_id": item.disease_id,
        "disease_name": item.disease.disease_name,
        "diagnosed_date": item.diagnosed_date.isoformat() if item.diagnosed_date else None,
        "current_status": item.current_status,
        "custom_disease_name": item.custom_disease_name,
        "notes": item.notes,
    }


def prescription_dict(item: Prescription, include_children: bool = False):
    result = {
        "prescription_id": item.prescription_id,
        "patient_disease_id": item.patient_disease_id,
        "disease_name": item.patient_disease.disease.disease_name,
        "facility_id": item.facility_id,
        "facility_name": item.facility.facility_name if item.facility_id else item.custom_facility_name,
        "prescription_date": item.prescription_date.isoformat(),
        "doctor_name": item.doctor_name,
        "custom_facility_name": item.custom_facility_name,
        "illness_location": item.illness_location,
        "advice": item.advice,
        "additional_notes": item.additional_notes,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
    if include_children:
        result["medicines"] = [
            {
                "medicine_id": row.medicine_id,
                "medicine_name": row.medicine.medicine_name,
                "brand_name": row.medicine.med_brand.brand_name,
                "type_name": row.medicine.med_type.med_type_name,
                "dosage": row.dosage,
                "times_per_day": row.times_per_day,
                "duration_days": row.duration_days,
                "start_date": row.start_date.isoformat() if row.start_date else None,
                "end_date": row.end_date.isoformat() if row.end_date else None,
                "course_completed": row.course_completed,
                "side_effects": row.side_effects,
                "effectiveness": row.effectiveness,
            }
            for row in item.medicine_entries.select_related(
                "medicine__med_brand", "medicine__med_type"
            ).all()
        ]
        result["tests"] = [
            {
                "test_id": row.test_id,
                "test_name": row.test.test_name,
                "completion_status": row.completion_status,
                "test_date": row.test_date.isoformat() if row.test_date else None,
                "diagnostic_center_name": row.diagnostic_center_name,
                "result_summary": row.result_summary,
                "custom_test_name": row.custom_test_name,
            }
            for row in item.test_entries.select_related("test").all()
        ]
        result["images"] = [
            {
                "image_id": image.image_id,
                "file_path": image.file_path,
                "file_size_kb": image.file_size_kb,
                "uploaded_at": image.uploaded_at.isoformat() if image.uploaded_at else None,
            }
            for image in item.images.all()
        ]
    return result


def submission_dict(item: MedicineSubmission):
    return {
        "submission_id": item.submission_id,
        "patient_id": item.patient_id,
        "patient_name": item.patient.user.full_name,
        "proposed_medicine_name": item.proposed_medicine_name,
        "med_brand_name": item.med_brand_name,
        "proposed_active_ingredient": item.proposed_active_ingredient,
        "status": item.status,
        "submitted_at": item.submitted_at.isoformat() if item.submitted_at else None,
        "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        "review_comments": item.review_comments,
        "approved_medicine_id": item.approved_medicine_id,
    }
