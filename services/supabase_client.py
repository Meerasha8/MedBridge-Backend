from supabase import create_client, Client
from config import settings

# Admin client (service role) — bypasses RLS, use only server-side
supabase_admin: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_ROLE_KEY,
)

# Anon client — for user-facing sign-in / sign-up
supabase_anon: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_ANON_KEY,
)
