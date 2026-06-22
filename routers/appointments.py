from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from services.mcp import call_tool
from services.supabase_client import supabase_admin

router = APIRouter(prefix="/appointments", tags=["Appointments"])


class BookAppointmentRequest(BaseModel):
    doctor_id: str
    scheduled_at: str  # ISO 8601 with +05:30
    symptoms_text: str
    symptoms_language: str = "en"
    is_urgent: bool = False


class CompleteAppointmentRequest(BaseModel):
    notes: str = ""


@router.post("")
async def book_appointment(body: BookAppointmentRequest, request: Request):
    role = request.state.role
    user_id = request.state.user_id
    if role != "patient":
        raise HTTPException(status_code=403, detail="Only patients can book appointments")

    # Get patient record
    patient = supabase_admin.table("patients").select("id").eq("profile_id", user_id).single().execute()
    if not patient.data:
        raise HTTPException(status_code=404, detail="Patient record not found")
    patient_id = patient.data["id"]

    result = await call_tool("book_appointment", {
        "patient_id": patient_id,
        "doctor_id": body.doctor_id,
        "scheduled_at": body.scheduled_at,
        "symptoms_text": body.symptoms_text,
        "symptoms_language": body.symptoms_language,
        "is_urgent": body.is_urgent,
    })
    return result


@router.get("")
async def list_appointments(request: Request):
    role = request.state.role
    user_id = request.state.user_id

    if role == "patient":
        patient = supabase_admin.table("patients").select("id").eq("profile_id", user_id).single().execute()
        if not patient.data:
            raise HTTPException(status_code=404, detail="Patient record not found")
        patient_id = patient.data["id"]
        result = supabase_admin.table("appointments") \
            .select("*, doctors(clinic_name), profiles(full_name)") \
            .eq("patient_id", patient_id) \
            .order("scheduled_at", desc=True) \
            .execute()
        return result.data

    elif role == "doctor":
        doctor = supabase_admin.table("doctors").select("id").eq("profile_id", user_id).single().execute()
        if not doctor.data:
            raise HTTPException(status_code=404, detail="Doctor record not found")
        doctor_id = doctor.data["id"]
        result = supabase_admin.table("appointments") \
            .select("*") \
            .eq("doctor_id", doctor_id) \
            .in_("status", ["pending", "confirmed"]) \
            .order("scheduled_at") \
            .execute()
        return result.data

    elif role in ("nurse", "receptionist"):
        # Find which doctor they belong to
        sub = supabase_admin.table("sub_accounts").select("doctor_id") \
            .eq("profile_id", user_id).eq("is_active", True).single().execute()
        if not sub.data:
            raise HTTPException(status_code=404, detail="Sub-account not found")
        doctor_id = sub.data["doctor_id"]
        result = supabase_admin.table("appointments") \
            .select("*") \
            .eq("doctor_id", doctor_id) \
            .in_("status", ["pending", "confirmed"]) \
            .order("scheduled_at") \
            .execute()
        return result.data

    raise HTTPException(status_code=403, detail="Unauthorized")


@router.get("/{appointment_id}")
async def get_appointment(appointment_id: str, request: Request):
    user_id = request.state.user_id
    role = request.state.role

    result = supabase_admin.table("appointments").select("*").eq("id", appointment_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appt = result.data

    # Access control: patient, doctor, or their staff
    if role == "patient":
        patient = supabase_admin.table("patients").select("id").eq("profile_id", user_id).single().execute()
        if not patient.data or patient.data["id"] != appt["patient_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
    elif role == "doctor":
        doctor = supabase_admin.table("doctors").select("id").eq("profile_id", user_id).single().execute()
        if not doctor.data or doctor.data["id"] != appt["doctor_id"]:
            raise HTTPException(status_code=403, detail="Access denied")
    # nurses/admin pass through

    return appt


class StatusUpdate(BaseModel):
    status: str  # confirmed | cancelled | completed
    notes: str = ""


@router.patch("/{appointment_id}/status")
async def update_appointment_status(
    appointment_id: str,
    body: StatusUpdate,
    request: Request,
):
    role = request.state.role
    user_id = request.state.user_id

    if role not in ("doctor", "nurse", "receptionist", "admin"):
        raise HTTPException(status_code=403, detail="Only medical staff can update appointment status")

    # Verify doctor access
    appt = supabase_admin.table("appointments").select("doctor_id").eq("id", appointment_id).single().execute()
    if not appt.data:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if body.status == "completed":
        # Find doctor_id for MCP call
        doctor_id = appt.data["doctor_id"]
        result = await call_tool("complete_appointment", {
            "appointment_id": appointment_id,
            "doctor_id": doctor_id,
            "notes": body.notes,
        })
        return result
    else:
        supabase_admin.table("appointments").update({"status": body.status}) \
            .eq("id", appointment_id).execute()
        return {"success": True, "status": body.status}
