from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from services.supabase_client import supabase_admin, supabase_anon

router = APIRouter(prefix="/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    phone: str | None = None
    role: str = "patient"  # patient | doctor | nurse | receptionist | admin
    language_preference: str = "en"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    # 1. Create Supabase auth user
    try:
        auth_resp = supabase_admin.auth.admin.create_user({
            "email": body.email,
            "password": body.password,
            "email_confirm": True,
            "user_metadata": {"role": body.role},
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    user_id = auth_resp.user.id

    # 2. Insert into profiles
    profile_data = {
        "id": user_id,
        "full_name": body.full_name,
        "phone": body.phone,
        "role": body.role,
        "language_preference": body.language_preference,
        "email": body.email,
    }
    try:
        supabase_admin.table("profiles").insert(profile_data).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profile insert failed: {e}")

    # 3. Role-specific inserts
    if body.role == "doctor":
        try:
            supabase_admin.table("doctors").insert({
                "profile_id": user_id,
                "is_verified": False,
            }).execute()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Doctor insert failed: {e}")

    elif body.role == "patient":
        try:
            supabase_admin.table("patients").insert({
                "profile_id": user_id,
            }).execute()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Patient insert failed: {e}")

    # 4. Sign in to get access token
    try:
        login_resp = supabase_anon.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login after register failed: {e}")

    return {
        "user_id": user_id,
        "access_token": login_resp.session.access_token,
        "role": body.role,
    }


@router.post("/login")
async def login(body: LoginRequest):
    try:
        resp = supabase_anon.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_id = resp.user.id
    role = resp.user.user_metadata.get("role", "patient")

    # Fetch full_name from profiles
    profile = supabase_admin.table("profiles").select("full_name").eq("id", user_id).single().execute()
    full_name = profile.data.get("full_name", "") if profile.data else ""

    return {
        "access_token": resp.session.access_token,
        "user_id": user_id,
        "role": role,
        "full_name": full_name,
    }


@router.post("/logout")
async def logout(request: Request):
    token = request.state.token
    try:
        supabase_anon.auth.sign_out()
    except Exception:
        pass
    return {"success": True}
