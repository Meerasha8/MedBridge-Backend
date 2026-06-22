from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime
from services.supabase_client import supabase_admin
from services.pdf_service import generate_prescription_pdf, upload_prescription_pdf

router = APIRouter(prefix="/prescriptions", tags=["Prescriptions"])


class Medicine(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: str
    instructions: str = ""


class CreatePrescriptionRequest(BaseModel):
    appointment_id: str
    medicines: list[Medicine]
    notes: str = ""


@router.post("")
async def create_prescription(body: CreatePrescriptionRequest, request: Request):
    role = request.state.role
    user_id = request.state.user_id

    if role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can create prescriptions")

    # Verify doctor owns this appointment
    doctor = supabase_admin.table("doctors").select("id").eq("profile_id", user_id).single().execute()
    if not doctor.data:
        raise HTTPException(status_code=404, detail="Doctor record not found")
    doctor_id = doctor.data["id"]

    appt = supabase_admin.table("appointments") \
        .select("*, patients(id, profiles(full_name))") \
        .eq("id", body.appointment_id) \
        .single() \
        .execute()
    if not appt.data or appt.data["doctor_id"] != doctor_id:
        raise HTTPException(status_code=403, detail="You don't have access to this appointment")

    # Get doctor name
    doc_profile = supabase_admin.table("profiles").select("full_name").eq("id", user_id).single().execute()
    doctor_name = doc_profile.data.get("full_name", "Doctor") if doc_profile.data else "Doctor"

    patient_name = "Patient"
    try:
        patient_name = appt.data["patients"]["profiles"]["full_name"]
    except (KeyError, TypeError):
        pass

    # 1. Insert prescription
    rx_insert = supabase_admin.table("prescriptions").insert({
        "appointment_id": body.appointment_id,
        "doctor_id": doctor_id,
        "notes": body.notes,
        "created_at": datetime.utcnow().isoformat(),
    }).execute()
    prescription_id = rx_insert.data[0]["id"]

    # 2. Insert medicines
    if body.medicines:
        med_rows = [
            {
                "prescription_id": prescription_id,
                **med.model_dump(),
            }
            for med in body.medicines
        ]
        supabase_admin.table("medicines").insert(med_rows).execute()

    # 3. Generate PDF
    pdf_bytes = generate_prescription_pdf(
        prescription_id=prescription_id,
        doctor_name=doctor_name,
        patient_name=patient_name,
        appointment_date=datetime.utcnow().strftime("%Y-%m-%d"),
        medicines=[med.model_dump() for med in body.medicines],
        notes=body.notes,
    )

    # 4. Upload PDF
    try:
        pdf_url = await upload_prescription_pdf(prescription_id, pdf_bytes)
    except Exception as e:
        pdf_url = ""  # Don't fail the whole request if storage fails

    # 5. Update prescription with pdf_url
    supabase_admin.table("prescriptions").update({"pdf_url": pdf_url}) \
        .eq("id", prescription_id).execute()

    # 6. Notify patient
    try:
        patient_profile_id = appt.data["patients"]["profiles"].get("id") or \
                              appt.data.get("patient_id")
        supabase_admin.table("notifications").insert({
            "user_id": patient_profile_id,
            "title": "New Prescription",
            "body": f"Dr. {doctor_name} has issued a prescription for your appointment.",
            "type": "prescription",
            "reference_id": prescription_id,
            "is_read": False,
        }).execute()
    except Exception:
        pass  # Notification failure shouldn't block response

    return {
        "prescription_id": prescription_id,
        "pdf_url": pdf_url,
        "success": True,
    }


@router.get("/{appointment_id}")
async def get_prescription(appointment_id: str, request: Request):
    role = request.state.role
    user_id = request.state.user_id

    # Verify access
    appt = supabase_admin.table("appointments").select("patient_id, doctor_id") \
        .eq("id", appointment_id).single().execute()
    if not appt.data:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if role == "patient":
        patient = supabase_admin.table("patients").select("id").eq("profile_id", user_id).single().execute()
        if not patient.data or patient.data["id"] != appt.data["patient_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
    elif role == "doctor":
        doctor = supabase_admin.table("doctors").select("id").eq("profile_id", user_id).single().execute()
        if not doctor.data or doctor.data["id"] != appt.data["doctor_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

    rx = supabase_admin.table("prescriptions") \
        .select("*, medicines(*)") \
        .eq("appointment_id", appointment_id) \
        .execute()

    return rx.data
