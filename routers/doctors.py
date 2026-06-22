from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel
from services.mcp import call_tool
from services.supabase_client import supabase_admin

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("/search")
async def search_doctors(
    symptoms: str = Query(...),
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(20),
    specialization: str | None = Query(None),
    language: str = Query("en"),
):
    payload = {
        "symptoms": symptoms,
        "language": language,
        "lat": lat,
        "lng": lng,
        "radius_km": radius_km,
    }
    if specialization:
        payload["specialization"] = specialization

    result = await call_tool("search_doctors", payload)
    return result


@router.get("/{doctor_id}")
async def get_doctor(doctor_id: str):
    result = await call_tool("get_doctor_profile", {"doctor_id": doctor_id})
    return result


@router.get("/{doctor_id}/availability")
async def get_availability(doctor_id: str, date: str = Query(...)):
    result = await call_tool("check_availability", {"doctor_id": doctor_id, "date": date})
    return result


@router.get("/{doctor_id}/ratings")
async def get_ratings(doctor_id: str):
    result = await call_tool("get_doctor_ratings", {"doctor_id": doctor_id})
    return result


class DoctorProfileUpdate(BaseModel):
    specialization: str | None = None
    clinic_name: str | None = None
    clinic_address: str | None = None
    languages_spoken: list[str] | None = None
    consultation_fee: float | None = None
    bio: str | None = None


@router.put("/profile")
async def update_doctor_profile(body: DoctorProfileUpdate, request: Request):
    role = request.state.role
    user_id = request.state.user_id
    if role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can update their profile")

    # Find doctor record by profile_id
    doc = supabase_admin.table("doctors").select("id").eq("profile_id", user_id).single().execute()
    if not doc.data:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    doctor_id = doc.data["id"]

    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    supabase_admin.table("doctors").update(update_data).eq("id", doctor_id).execute()
    return {"success": True}
