from fastapi import Request, status
from fastapi.responses import JSONResponse
from jose import jwt, JWTError
from config import settings

PUBLIC_ROUTES = {
    ("POST", "/auth/register"),
    ("POST", "/auth/login"),
    ("GET", "/health"),
    ("HEAD", "/health"),
    ("GET", "/"),
    ("HEAD", "/"),
    ("GET", "/favicon.ico"),
    ("HEAD", "/favicon.ico"),
    ("GET", "/docs"),
    ("GET", "/openapi.json"),
    ("GET", "/redoc"),
}

PUBLIC_PREFIXES = [
    "/doctors/search",
    "/doctors/",
]


def is_public(method: str, path: str) -> bool:
    if (method, path) in PUBLIC_ROUTES:
        return True
    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


async def auth_middleware(request: Request, call_next):
    path = request.url.path
    method = request.method

    if is_public(method, path):
        return await call_next(request)

    if path.startswith("/chat/ws"):
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Missing or invalid Authorization header"},
        )

    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
        request.state.user_id = payload.get("sub")
        request.state.role = payload.get("user_metadata", {}).get("role", "patient")
        request.state.token = token
    except JWTError as e:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": f"Invalid token: {str(e)}"},
        )

    return await call_next(request)


def decode_token(token: str) -> dict:
    payload = jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )
    return payload
