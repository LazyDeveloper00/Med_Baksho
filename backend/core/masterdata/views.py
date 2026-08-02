from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.decorators import role_required
from core.http import fail, ok, read_payload
from core.models import (
    Disease,
    MedicalFacility,
    MedicalFacilityType,
    MedicalTest,
    Medicine,
    MedicineBrand,
    MedicineType,
    TestCategory,
)


@require_GET
def list_master_data(request):
    data = {
        "diseases": list(
            Disease.objects.filter(is_active=True).values("disease_id", "disease_name")
        ),
        "facility_types": list(
            MedicalFacilityType.objects.values("facility_type_id", "facility_type_name")
        ),
        "facilities": list(
            MedicalFacility.objects.filter(is_active=True).values(
                "facility_id", "facility_name", "facility_type_id"
            )
        ),
        "medicine_brands": list(MedicineBrand.objects.values("brand_id", "brand_name")),
        "medicine_types": list(MedicineType.objects.values("med_type_id", "med_type_name")),
        "medicines": list(
            Medicine.objects.filter(is_active=True).values(
                "medicine_id",
                "medicine_name",
                "main_active_ingredient",
                "med_brand_id",
                "med_type_id",
            )
        ),
        "test_categories": list(
            TestCategory.objects.filter(is_active=True).values("category_id", "category_name")
        ),
        "medical_tests": list(
            MedicalTest.objects.filter(is_active=True).values(
                "test_id", "category_id", "test_name", "description"
            )
        ),
    }
    return ok(data)


@csrf_exempt
@require_POST
@role_required("admin")
def create_master_data(request, entity: str):
    try:
        data = read_payload(request)
        if entity == "disease":
            item = Disease.objects.create(
                disease_name=str(data["disease_name"]).strip(), is_active=True
            )
            result = {"disease_id": item.disease_id, "disease_name": item.disease_name}
        elif entity == "facility-type":
            item = MedicalFacilityType.objects.create(
                facility_type_name=str(data["facility_type_name"]).strip()
            )
            result = {
                "facility_type_id": item.facility_type_id,
                "facility_type_name": item.facility_type_name,
            }
        elif entity == "facility":
            facility_type = MedicalFacilityType.objects.get(
                facility_type_id=int(data["facility_type_id"])
            )
            item = MedicalFacility.objects.create(
                facility_name=str(data["facility_name"]).strip(),
                facility_type=facility_type,
                is_active=True,
            )
            result = {"facility_id": item.facility_id, "facility_name": item.facility_name}
        elif entity == "medicine-brand":
            item = MedicineBrand.objects.create(
                brand_name=str(data["brand_name"]).strip()
            )
            result = {"brand_id": item.brand_id, "brand_name": item.brand_name}
        elif entity == "medicine-type":
            item = MedicineType.objects.create(
                med_type_name=str(data["med_type_name"]).strip()
            )
            result = {"med_type_id": item.med_type_id, "med_type_name": item.med_type_name}
        elif entity == "test-category":
            item = TestCategory.objects.create(
                category_name=str(data["category_name"]).strip(), is_active=True
            )
            result = {"category_id": item.category_id, "category_name": item.category_name}
        elif entity == "medical-test":
            category = TestCategory.objects.get(category_id=int(data["category_id"]))
            item = MedicalTest.objects.create(
                category=category,
                test_name=str(data["test_name"]).strip(),
                description=(data.get("description") or "").strip() or None,
                is_active=True,
            )
            result = {"test_id": item.test_id, "test_name": item.test_name}
        elif entity == "medicine":
            brand = MedicineBrand.objects.get(brand_id=int(data["brand_id"]))
            med_type = MedicineType.objects.get(med_type_id=int(data["med_type_id"]))
            item = Medicine.objects.create(
                medicine_name=str(data["medicine_name"]).strip(),
                main_active_ingredient=(data.get("main_active_ingredient") or "").strip()
                or None,
                med_brand=brand,
                med_type=med_type,
                is_active=True,
            )
            result = {"medicine_id": item.medicine_id, "medicine_name": item.medicine_name}
        else:
            return fail("Unsupported master-data entity.", 404)
        if not next((v for k, v in result.items() if k.endswith("name")), True):
            return fail("Name cannot be empty.", 400)
        return ok(result, 201)
    except KeyError as exc:
        return fail(f"Missing required field: {exc.args[0]}", 400)
    except (ValueError, IntegrityError) as exc:
        return fail("Invalid or duplicate master-data record.", 409, details=str(exc))
    except (MedicalFacilityType.DoesNotExist, TestCategory.DoesNotExist, MedicineBrand.DoesNotExist, MedicineType.DoesNotExist):
        return fail("Referenced master-data record was not found.", 404)


MODEL_MAP = {
    "disease": (Disease, "disease_id"),
    "facility": (MedicalFacility, "facility_id"),
    "medicine": (Medicine, "medicine_id"),
    "test-category": (TestCategory, "category_id"),
    "medical-test": (MedicalTest, "test_id"),
}


@csrf_exempt
@require_POST
@role_required("admin")
def set_active(request, entity: str, object_id: int):
    model_info = MODEL_MAP.get(entity)
    if not model_info:
        return fail("Unsupported master-data entity.", 404)
    try:
        data = read_payload(request)
        if "is_active" not in data:
            return fail("is_active is required.", 400)
        value = data["is_active"]
        if isinstance(value, str):
            value = value.lower() in {"1", "true", "yes", "on"}
        model, pk_field = model_info
        updated = model.objects.filter(**{pk_field: object_id}).update(is_active=bool(value))
        if not updated:
            return fail("Record not found.", 404)
        return ok({"entity": entity, "id": object_id, "is_active": bool(value)})
    except ValueError as exc:
        return fail(str(exc), 400)
