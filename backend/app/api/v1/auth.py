import hmac
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, require_roles
from app.core.config import settings
from app.core.security import create_jwt, decode_jwt, hash_otp
from app.models.entities import OtpChallenge, RefreshSession, User
from app.schemas.auth import (
    OtpRequestResponse,
    PhoneRequest,
    ProfileUpdate,
    RefreshRequest,
    RoleChangeRequest,
    TokenResponse,
    UserResponse,
    VerifyOtpRequest,
)

router = APIRouter(tags=["Authentication"])
SIMULATED_OTP = "1234"
MAX_OTP_ATTEMPTS = 5


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def issue_tokens(session: Session, user: User) -> TokenResponse:
    access_token, _, _ = create_jwt(
        user.id,
        "access",
        timedelta(minutes=settings.access_token_minutes),
    )
    refresh_token, token_id, refresh_expires_at = create_jwt(
        user.id,
        "refresh",
        timedelta(days=settings.refresh_token_days),
    )
    session.add(
        RefreshSession(
            token_id=token_id,
            user_id=user.id,
            expires_at=refresh_expires_at,
        )
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/auth/register",
    response_model=OtpRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="GSM numarasıyla kayıt/giriş için OTP iste",
)
def request_otp(
    payload: PhoneRequest,
    session: Session = Depends(get_db),
) -> OtpRequestResponse:
    now = utc_now()
    challenge = session.scalar(
        select(OtpChallenge).where(
            OtpChallenge.phone_number == payload.phone_number
        )
    )
    if challenge is None:
        challenge = OtpChallenge(
            phone_number=payload.phone_number,
            code_hash=hash_otp(payload.phone_number, SIMULATED_OTP),
            attempts=0,
            created_at=now,
            expires_at=now + timedelta(minutes=settings.otp_expiration_minutes),
        )
        session.add(challenge)
    else:
        challenge.code_hash = hash_otp(payload.phone_number, SIMULATED_OTP)
        challenge.attempts = 0
        challenge.created_at = now
        challenge.expires_at = now + timedelta(minutes=settings.otp_expiration_minutes)
        challenge.consumed_at = None

    session.commit()
    return OtpRequestResponse(
        message="SMS gönderimi simüle edildi; doğrulama kodu sabit 1234'tür.",
        simulation_code=SIMULATED_OTP,
        expires_in_seconds=settings.otp_expiration_minutes * 60,
    )


@router.post(
    "/auth/verify-otp",
    response_model=TokenResponse,
    summary="OTP'yi doğrula ve JWT token'larını al",
)
def verify_otp(
    payload: VerifyOtpRequest,
    session: Session = Depends(get_db),
) -> TokenResponse:
    challenge = session.scalar(
        select(OtpChallenge).where(
            OtpChallenge.phone_number == payload.phone_number
        )
    )
    now = utc_now()
    if challenge is None or challenge.consumed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aktif OTP isteği bulunamadı; yeniden kod isteyin.",
        )
    if challenge.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP süresi doldu; yeniden kod isteyin.",
        )
    if challenge.attempts >= MAX_OTP_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Çok fazla hatalı deneme yapıldı; yeni kod isteyin.",
        )
    if not hmac.compare_digest(
        challenge.code_hash,
        hash_otp(payload.phone_number, payload.otp),
    ):
        challenge.attempts += 1
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP kodu hatalı.",
        )

    user = session.scalar(
        select(User).where(User.phone_number == payload.phone_number)
    )
    if user is None:
        legacy_phone_number = f"0{payload.phone_number[3:]}"
        user = session.scalar(
            select(User).where(User.phone_number == legacy_phone_number)
        )
        if user is not None:
            user.phone_number = payload.phone_number

    if user is None:
        role = (
            "ADMIN"
            if payload.phone_number == settings.bootstrap_admin_phone
            else "CUSTOMER"
        )
        user = User(
            phone_number=payload.phone_number,
            first_name="",
            last_name="",
            role=role,
        )
        session.add(user)
        session.flush()
    elif payload.phone_number == settings.bootstrap_admin_phone:
        user.role = "ADMIN"

    challenge.consumed_at = now
    response = issue_tokens(session, user)
    session.commit()
    return response


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="Access token'ı yenile ve refresh token'ı döndür",
)
def refresh_tokens(
    payload: RefreshRequest,
    session: Session = Depends(get_db),
) -> TokenResponse:
    claims = decode_jwt(payload.refresh_token, "refresh")
    try:
        user_id = int(claims["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token kullanıcı bilgisi geçersiz.",
        ) from exc

    token_id = claims.get("jti")
    if not isinstance(token_id, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token oturumu geçersiz.",
        )
    refresh_session = session.get(RefreshSession, token_id)
    if (
        refresh_session is None
        or refresh_session.user_id != user_id
        or refresh_session.revoked_at is not None
        or refresh_session.expires_at <= utc_now()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token geçersiz, kullanılmış veya süresi dolmuş.",
        )

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı.",
        )

    refresh_session.revoked_at = utc_now()
    response = issue_tokens(session, user)
    session.commit()
    return response


@router.get(
    "/auth/me",
    response_model=UserResponse,
    summary="Oturum açmış kullanıcının profilini getir",
)
def get_my_profile(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)


@router.patch(
    "/auth/me",
    response_model=UserResponse,
    summary="Profil, kahve tercihleri ve alerjenleri güncelle",
)
def update_my_profile(
    payload: ProfileUpdate,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserResponse:
    updates = payload.model_dump(exclude_unset=True)
    preferences = dict(user.preferences or {})
    for field in ("coffee_preferences", "allergens"):
        if field in updates:
            preferences[field] = updates.pop(field)
    for field, value in updates.items():
        setattr(user, field, value)
    if preferences:
        user.preferences = preferences

    session.commit()
    session.refresh(user)
    return UserResponse.model_validate(user)


@router.patch(
    "/admin/users/{user_id}/role",
    response_model=UserResponse,
    summary="Kullanıcı rolünü müşteri veya dükkân sahibi olarak değiştir",
    dependencies=[Depends(require_roles("ADMIN"))],
)
def change_user_role(
    user_id: int,
    payload: RoleChangeRequest,
    session: Session = Depends(get_db),
) -> UserResponse:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı.",
        )
    user.role = payload.role
    session.commit()
    session.refresh(user)
    return UserResponse.model_validate(user)
