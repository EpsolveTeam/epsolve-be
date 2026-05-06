import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
    verify_refresh_token,
)
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from app.services.email_service import send_password_reset_email

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, session: Session = Depends(get_session)):
    existing = session.exec(select(User).where(User.email == body.email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    refresh_token = create_refresh_token(user.id)
    user.refresh_token_hash = hash_refresh_token(refresh_token)
    session.add(user)
    session.commit()

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == body.email)).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")

    refresh_token = create_refresh_token(user.id)
    user.refresh_token_hash = hash_refresh_token(refresh_token)
    session.add(user)
    session.commit()

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token,
    )

@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    current_user.refresh_token_hash = None
    session.add(current_user)
    session.commit()
    return {"message": "Successfully logged out"}

@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, session: Session = Depends(get_session)):
    user_id = decode_refresh_token(body.refresh_token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = session.exec(select(User).where(User.id == user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    if not user.refresh_token_hash or not verify_refresh_token(body.refresh_token, user.refresh_token_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")

    refresh_token = create_refresh_token(user.id)
    user.refresh_token_hash = hash_refresh_token(refresh_token)
    session.add(user)
    session.commit()

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token,
    )


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(body: ForgotPasswordRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == body.email)).first()
    # Selalu return sukses agar email valid/tidak valid tidak bisa ditebak
    if not user or not user.is_active:
        return {"message": "Jika email terdaftar, link reset password telah dikirim."}

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    user.password_reset_token = token_hash
    user.password_reset_token_expiry = datetime.utcnow() + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)
    session.add(user)
    session.commit()

    reset_url = f"{settings.FRONTEND_URL}?reset_token={token}"
    send_password_reset_email(user.email, user.full_name, reset_url)

    return {"message": "Jika email terdaftar, link reset password telah dikirim."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(body: ResetPasswordRequest, session: Session = Depends(get_session)):
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    user = session.exec(select(User).where(User.password_reset_token == token_hash)).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token tidak valid atau sudah digunakan.")

    expiry = user.password_reset_token_expiry
    if not expiry or datetime.utcnow() > expiry.replace(tzinfo=None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token sudah kadaluarsa. Silakan minta reset password baru.")

    user.hashed_password = hash_password(body.new_password)
    user.password_reset_token = None
    user.password_reset_token_expiry = None
    user.refresh_token_hash = None  # invalidate semua sesi aktif
    session.add(user)
    session.commit()

    return {"message": "Password berhasil direset. Silakan masuk dengan password baru."}
