from fastapi import APIRouter, HTTPException, Request
from services.mcp import call_tool
from services.supabase_client import supabase_admin

router = APIRouter(prefix="/admin", tags=["Admin"])


def _require_admin(request: Request):
    if request.state.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/pending-doctors")
async def pending_doctors(request: Request):
    _require_admin(request)
    result = supabase_admin.table("doctors") \
        .select("*, profiles(full_name, email, phone)") \
        .eq("is_verified", False) \
        .execute()
    return result.data


@router.patch("/doctors/{doctor_id}/verify")
async def verify_doctor(doctor_id: str, request: Request):
    _require_admin(request)
    supabase_admin.table("doctors") \
        .update({"is_verified": True}) \
        .eq("id", doctor_id) \
        .execute()

    # Write audit log
    supabase_admin.table("audit_logs").insert({
        "action": "doctor_verified",
        "actor_id": request.state.user_id,
        "reference_id": doctor_id,
        "details": f"Doctor {doctor_id} verified by admin {request.state.user_id}",
    }).execute()

    return {"success": True}


@router.get("/audit-logs")
async def audit_logs(request: Request):
    _require_admin(request)
    result = supabase_admin.table("audit_logs") \
        .select("*") \
        .order("created_at", desc=True) \
        .limit(100) \
        .execute()
    return result.data


@router.post("/cleanup")
async def cleanup_shared_data(request: Request):
    _require_admin(request)
    result = await call_tool("cleanup_expired_shared_data", {})
    return result
