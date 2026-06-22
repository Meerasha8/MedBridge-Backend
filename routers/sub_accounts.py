from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from services.supabase_client import supabase_admin, supabase_anon

router = APIRouter(prefix="/sub-accounts", tags=["Sub-accounts"])


class CreateSubAccountRequest(BaseModel):
    email: EmailStr
    full_name: str
    phone: str | None = None
    role: str  # nurse | receptionist


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_sub_account(body: CreateSubAccountRequest, request: Request):
    role = request.state.role
    user_id = request.state.user_id

    if role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can create sub-accounts")

    if body.role not in ("nurse", "receptionist"):
        raise HTTPException(status_code=400, detail="Role must be 'nurse' or 'receptionist'")

    # Get doctor record
    doctor = supabase_admin.table("doctors").select("id").eq("profile_id", user_id).single().execute()
    if not doctor.data:
        raise HTTPException(status_code=404, detail="Doctor record not found")
    doctor_id = doctor.data["id"]

    # Create auth user with temporary password (they should reset it)
    import secrets
    temp_password = secrets.token_urlsafe(16)

    try:
        auth_resp = supabase_admin.auth.admin.create_user({
            "email": body.email,
            "password": temp_password,
            "email_confirm": True,
            "user_metadata": {"role": body.role},
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    new_user_id = auth_resp.user.id

    # Insert profile
    supabase_admin.table("profiles").insert({
        "id": new_user_id,
        "full_name": body.full_name,
        "phone": body.phone,
        "role": body.role,
        "email": body.email,
    }).execute()

    # Insert sub_accounts record
    supabase_admin.table("sub_accounts").insert({
        "profile_id": new_user_id,
        "doctor_id": doctor_id,
        "role": body.role,
        "is_active": True,
    }).execute()

    return {
        "sub_account_id": new_user_id,
        "email": body.email,
        "role": body.role,
        "temp_password": temp_password,
        "message": "Sub-account created. Share the temp_password with the user to log in.",
    }


@router.get("")
async def list_sub_accounts(request: Request):
    role = request.state.role
    user_id = request.state.user_id

    if role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can view sub-accounts")

    doctor = supabase_admin.table("doctors").select("id").eq("profile_id", user_id).single().execute()
    if not doctor.data:
        raise HTTPException(status_code=404, detail="Doctor record not found")
    doctor_id = doctor.data["id"]

    result = supabase_admin.table("sub_accounts") \
        .select("*, profiles(full_name, email, phone)") \
        .eq("doctor_id", doctor_id) \
        .execute()
    return result.data


@router.delete("/{sub_account_id}")
async def delete_sub_account(sub_account_id: str, request: Request):
    role = request.state.role
    user_id = request.state.user_id

    if role != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can deactivate sub-accounts")

    doctor = supabase_admin.table("doctors").select("id").eq("profile_id", user_id).single().execute()
    if not doctor.data:
        raise HTTPException(status_code=404, detail="Doctor record not found")
    doctor_id = doctor.data["id"]

    # Verify this sub-account belongs to this doctor
    sub = supabase_admin.table("sub_accounts") \
        .select("id").eq("profile_id", sub_account_id).eq("doctor_id", doctor_id).single().execute()
    if not sub.data:
        raise HTTPException(status_code=404, detail="Sub-account not found or access denied")

    supabase_admin.table("sub_accounts").update({"is_active": False}) \
        .eq("profile_id", sub_account_id).execute()

    return {"success": True, "message": "Sub-account deactivated"}
