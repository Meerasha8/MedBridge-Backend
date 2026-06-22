from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from services.mcp import call_tool
from services.supabase_client import supabase_admin

router = APIRouter(prefix="/reviews", tags=["Reviews"])


class SubmitReviewRequest(BaseModel):
    appointment_id: str
    rating: int  # 1-5
    feedback_text: str = ""
    feedback_language: str = "en"


@router.post("")
async def submit_review(body: SubmitReviewRequest, request: Request):
    role = request.state.role
    user_id = request.state.user_id

    if role != "patient":
        raise HTTPException(status_code=403, detail="Only patients can submit reviews")

    if body.rating < 1 or body.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    patient = supabase_admin.table("patients").select("id").eq("profile_id", user_id).single().execute()
    if not patient.data:
        raise HTTPException(status_code=404, detail="Patient record not found")
    patient_id = patient.data["id"]

    result = await call_tool("submit_review", {
        "appointment_id": body.appointment_id,
        "patient_id": patient_id,
        "rating": body.rating,
        "feedback_text": body.feedback_text,
        "feedback_language": body.feedback_language,
    })
    return result
