from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from services.mcp import call_tool
from services.supabase_client import supabase_admin

router = APIRouter(prefix="/documents", tags=["Documents"])


class UploadMetaRequest(BaseModel):
    patient_id: str
    appointment_id: str | None = None
    doc_type: str
    file_url: str
    file_name: str
    description: str = ""


class GrantAccessRequest(BaseModel):
    doctor_id: str


@router.post("/upload-meta")
async def upload_document_meta(body: UploadMetaRequest, request: Request):
    role = request.state.role
    user_id = request.state.user_id

    if role not in ("nurse", "doctor", "patient"):
        raise HTTPException(status_code=403, detail="Only nurses, doctors, or patients can upload documents")

    result = await call_tool("upload_document_meta", {
        "patient_id": body.patient_id,
        "uploaded_by": user_id,
        "appointment_id": body.appointment_id,
        "doc_type": body.doc_type,
        "file_url": body.file_url,
        "file_name": body.file_name,
        "description": body.description,
    })
    return result


@router.get("")
async def list_documents(request: Request):
    role = request.state.role
    user_id = request.state.user_id

    if role == "patient":
        patient = supabase_admin.table("patients").select("id").eq("profile_id", user_id).single().execute()
        if not patient.data:
            raise HTTPException(status_code=404, detail="Patient record not found")
        patient_id = patient.data["id"]
        result = await call_tool("get_patient_reports", {
            "patient_id": patient_id,
            "requesting_doctor_id": "self",
        })
        # For patients requesting their own docs, bypass consent check via direct DB query
        docs = supabase_admin.table("patient_documents") \
            .select("*") \
            .eq("patient_id", patient_id) \
            .order("created_at", desc=True) \
            .execute()
        return docs.data

    elif role == "doctor":
        doctor = supabase_admin.table("doctors").select("id").eq("profile_id", user_id).single().execute()
        if not doctor.data:
            raise HTTPException(status_code=404, detail="Doctor record not found")
        # Return documents granted to this doctor — frontend should pass patient_id as query param
        # For now return empty — doctor should query per patient appointment
        return []

    raise HTTPException(status_code=403, detail="Unauthorized")


@router.post("/{document_id}/grant-access")
async def grant_access(document_id: str, body: GrantAccessRequest, request: Request):
    role = request.state.role
    user_id = request.state.user_id

    if role != "patient":
        raise HTTPException(status_code=403, detail="Only patients can grant document access")

    # Verify document belongs to this patient
    patient = supabase_admin.table("patients").select("id").eq("profile_id", user_id).single().execute()
    if not patient.data:
        raise HTTPException(status_code=404, detail="Patient record not found")

    doc = supabase_admin.table("patient_documents").select("id, patient_id") \
        .eq("id", document_id).single().execute()
    if not doc.data or doc.data["patient_id"] != patient.data["id"]:
        raise HTTPException(status_code=403, detail="You don't own this document")

    # Insert grant
    supabase_admin.table("document_access").insert({
        "document_id": document_id,
        "doctor_id": body.doctor_id,
        "granted_by": patient.data["id"],
        "revoked": False,
    }).execute()

    return {"success": True}


@router.delete("/{document_id}/revoke-access/{doctor_id}")
async def revoke_access(document_id: str, doctor_id: str, request: Request):
    role = request.state.role
    user_id = request.state.user_id

    if role != "patient":
        raise HTTPException(status_code=403, detail="Only patients can revoke document access")

    patient = supabase_admin.table("patients").select("id").eq("profile_id", user_id).single().execute()
    if not patient.data:
        raise HTTPException(status_code=404, detail="Patient record not found")

    supabase_admin.table("document_access") \
        .update({"revoked": True}) \
        .eq("document_id", document_id) \
        .eq("doctor_id", doctor_id) \
        .execute()

    return {"success": True}
