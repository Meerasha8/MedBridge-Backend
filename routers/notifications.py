from fastapi import APIRouter, HTTPException, Request
from services.supabase_client import supabase_admin

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("")
async def list_notifications(request: Request):
    user_id = request.state.user_id
    result = supabase_admin.table("notifications") \
        .select("*") \
        .eq("user_id", user_id) \
        .eq("is_read", False) \
        .order("created_at", desc=True) \
        .limit(50) \
        .execute()
    return result.data


@router.patch("/{notification_id}/read")
async def mark_read(notification_id: str, request: Request):
    user_id = request.state.user_id

    notif = supabase_admin.table("notifications") \
        .select("user_id").eq("id", notification_id).single().execute()
    if not notif.data or notif.data["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Notification not found")

    supabase_admin.table("notifications") \
        .update({"is_read": True}) \
        .eq("id", notification_id) \
        .execute()
    return {"success": True}
