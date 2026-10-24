from fastapi import APIRouter, Request, Response

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.exceptions import TooManyAttemptsError
from app.core.rate_limit import LoginRateLimiter
from app.schemas.auth import LoginRequest, RegisterRequest, UserOut
from app.services.auth import (
    SESSION_COOKIE,
    authenticate,
    end_session,
    register_user,
    start_session,
)

router = APIRouter(prefix="/auth", tags=["auth"])
login_limiter = LoginRateLimiter()


def _cookie_options() -> dict:
    return {"httponly": True, "samesite": "lax", "secure": get_settings().cookie_secure, "path": "/"}


def _set_session_cookie(response: Response, token: str) -> None:
    max_age = get_settings().session_days * 24 * 3600
    response.set_cookie(SESSION_COOKIE, token, max_age=max_age, **_cookie_options())


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterRequest, response: Response, db: DbSession):
    user = register_user(db, body.email, body.password)
    _set_session_cookie(response, start_session(db, user))
    return UserOut.model_validate(user)


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, request: Request, response: Response, db: DbSession):
    client_ip = request.client.host if request.client else "unknown"
    key = f"{client_ip}|{body.email}"
    if login_limiter.is_blocked(key):
        raise TooManyAttemptsError("Too many failed attempts. Please try again in a few minutes.")

    try:
        user = authenticate(db, body.email, body.password)
    except Exception:
        login_limiter.record_failure(key)
        raise

    login_limiter.reset(key)
    _set_session_cookie(response, start_session(db, user))
    return UserOut.model_validate(user)


@router.post("/logout", status_code=204)
def logout(request: Request, db: DbSession):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        end_session(db, token)
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, **_cookie_options())
    return response


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return UserOut.model_validate(user)