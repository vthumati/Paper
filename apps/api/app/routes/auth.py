import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user
from ..models.identity import User
from ..ratelimit import login_limiter, signup_limiter
from ..schemas import LoginIn, SignupIn, TokenOut, UserOut, VerifyEmailIn
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    if signup_limiter.blocked(ip):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many signups; try again later"
        )
    signup_limiter.record_failure(ip)  # every attempt counts toward the window
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    required = settings.email_verification_required
    token = secrets.token_urlsafe(24) if required else None
    user = User(
        email=body.email,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        email_verified=not required,
        email_verification_token=token,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    if token:
        # MVP shim for email delivery (HLD defers to OIDC/OTP): the token would
        # be emailed; here it is logged so a verify link can be completed.
        print(f"[email-verification] token for {user.email}: {token}")
    return user


@router.post("/verify-email", response_model=UserOut)
def verify_email(body: VerifyEmailIn, db: Session = Depends(get_db)):
    """Present the emailed token to prove ownership and unlock email-matched
    cross-tenant access (investor portal, advisor console)."""
    user = db.query(User).filter_by(email_verification_token=body.token).first()
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired verification token")
    user.email_verified = True
    user.email_verification_token = None
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    key = body.email.lower()
    if login_limiter.blocked(key):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed attempts; try again later",
        )
    user = db.query(User).filter_by(email=body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        login_limiter.record_failure(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    login_limiter.reset(key)
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/refresh", response_model=TokenOut)
def refresh(user: User = Depends(get_current_user)):
    """Exchange a valid (unexpired) token for a fresh one."""
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
