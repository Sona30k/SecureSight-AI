from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    CurrentUser, create_token, decode_token, hash_password, hash_token,
    needs_password_rehash, require_roles, verify_password,
)
from app.config.settings import settings
from app.database import get_db
from app.models import (
    AccountStatus, AuditLog, Notification, OTP, Permission, RefreshToken,
    RolePermission, User, UserRole, UserSession,
)
from app.schemas import (
    AccountDeleteRequest, AdminAccountAction, AssignRoleRequest, AuthDispatchResponse,
    ChangePasswordRequest, EmailVerifyRequest, ForgotPasswordRequest, LoginRequest,
    Message, OTPRequest, OTPVerifyRequest, RefreshRequest, RegisterRequest,
    ResetPasswordRequest, SessionRead, TokenPair, UserRead, UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
DB = Annotated[AsyncSession, Depends(get_db)]
AdminUser = Annotated[User, Depends(require_roles(UserRole.administrator))]
REFRESH_COOKIE = "shieldiq_refresh"
LOCKOUT_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
OTP_MINUTES = 10


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _cookie(response: Response, token: str, remember_me: bool) -> None:
    response.set_cookie(
        REFRESH_COOKIE, token, httponly=True, secure=settings.environment == "production",
        samesite="lax", path="/auth", max_age=(30 if remember_me else settings.refresh_token_days) * 86_400,
    )


async def _issue_tokens(
    user: User, db: AsyncSession, request: Request, *, remember_me: bool,
    session: UserSession | None = None,
) -> TokenPair:
    now = datetime.now(timezone.utc)
    session_days = 30 if remember_me else settings.refresh_token_days
    if session is None:
        session = UserSession(
            user_id=user.id, ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:500],
            device_name=request.headers.get("x-device-name", "Web browser")[:120],
            remember_me=remember_me, expires_at=now + timedelta(days=session_days),
        )
        db.add(session)
        await db.flush()
    refresh_jti = secrets.token_urlsafe(24)
    access, expires = create_token(
        user.id, user.token_version, "access", session_id=session.id,
    )
    refresh, refresh_seconds = create_token(
        user.id, user.token_version, "refresh", session_id=session.id,
        jti=refresh_jti, remember_me=remember_me,
    )
    db.add(RefreshToken(
        user_id=user.id, session_id=session.id, jti=refresh_jti,
        token_hash=hash_token(refresh), expires_at=now + timedelta(seconds=refresh_seconds),
    ))
    return TokenPair(
        access_token=access, refresh_token=refresh, expires_in=expires, session_id=session.id,
    )


async def _audit(
    db: AsyncSession, user_id: UUID | None, action: str, request: Request,
    details=None, *, outcome: str = "success",
) -> None:
    db.add(AuditLog(
        user_id=user_id, action=action, status=outcome, resource="user",
        resource_id=str(user_id) if user_id else None,
        ip_address=request.client.host if request.client else None, details=details or {},
    ))


async def _dispatch_email_verification(user: User, db: AsyncSession) -> str:
    token, _ = create_token(user.id, user.token_version, "email_verify")
    db.add(Notification(
        channel="email", recipient=user.email, subject="Verify your ShieldIQ account",
        body="Use the secure verification link to verify your ShieldIQ email address.",
        status="queued", metadata_={"verification_token": token},
    ))
    return token


async def _create_otp(
    db: AsyncSession, destination: str, purpose: str, user: User | None,
) -> str:
    now = datetime.now(timezone.utc)
    previous = list((await db.scalars(select(OTP).where(
        OTP.destination == destination, OTP.purpose == purpose, OTP.consumed_at.is_(None),
    ))).all())
    for item in previous:
        item.consumed_at = now
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(OTP(
        user_id=user.id if user else None, destination=destination, purpose=purpose,
        code_hash=hash_token(code), expires_at=now + timedelta(minutes=OTP_MINUTES),
    ))
    db.add(Notification(
        channel="sms" if purpose == "phone_verification" else "email",
        recipient=destination, subject="ShieldIQ verification code",
        body=f"Your ShieldIQ verification code is {code}. It expires in {OTP_MINUTES} minutes.",
        status="queued", metadata_={"purpose": purpose, "mock_delivery": True},
    ))
    return code


async def _consume_otp(db: AsyncSession, destination: str, purpose: str, code: str) -> OTP:
    item = await db.scalar(select(OTP).where(
        OTP.destination == destination, OTP.purpose == purpose, OTP.consumed_at.is_(None),
    ).order_by(OTP.created_at.desc()))
    now = datetime.now(timezone.utc)
    if not item or _aware(item.expires_at) <= now:
        raise HTTPException(status_code=400, detail="OTP is invalid or expired")
    item.attempts += 1
    if item.attempts > 5:
        item.consumed_at = now
        await db.commit()
        raise HTTPException(status_code=429, detail="Too many invalid OTP attempts")
    if not secrets.compare_digest(item.code_hash, hash_token(code)):
        await db.commit()
        raise HTTPException(status_code=400, detail="OTP is invalid or expired")
    item.consumed_at = now
    return item


def _activate_if_ready(user: User) -> None:
    if not (user.email_verified and user.phone_verified):
        return
    if user.role == UserRole.citizen:
        user.account_status = AccountStatus.verified
        user.is_active = True
    elif user.account_status not in {AccountStatus.rejected, AccountStatus.blocked}:
        user.account_status = AccountStatus.pending
        user.is_active = False


@router.post("/register", response_model=UserRead, status_code=201)
async def register(payload: RegisterRequest, request: Request, db: DB):
    if payload.role == UserRole.administrator:
        raise HTTPException(status_code=403, detail="Administrator accounts can only be created by an existing administrator")
    email = payload.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email is already registered")
    if payload.phone and await db.scalar(select(User.id).where(User.phone == payload.phone)):
        raise HTTPException(status_code=409, detail="Phone number is already registered")
    legacy_demo = settings.demo_mode and not payload.phone
    if not legacy_demo:
        if not payload.phone:
            raise HTTPException(status_code=422, detail="Phone number is required")
        if payload.role == UserRole.police and not payload.badge_number:
            raise HTTPException(status_code=422, detail="Badge number is required for police registration")
        if payload.role in {UserRole.bank, UserRole.telecom_provider} and not payload.employee_id:
            raise HTTPException(status_code=422, detail="Employee ID is required for organization registration")
    user = User(
        email=email, full_name=payload.full_name, phone=payload.phone,
        hashed_password=hash_password(payload.password), role=payload.role,
        account_status=AccountStatus.verified if legacy_demo else AccountStatus.pending,
        is_active=legacy_demo, email_verified=legacy_demo, phone_verified=legacy_demo,
        state=payload.state, district=payload.district,
        preferred_language=payload.preferred_language, organization=payload.organization,
        employee_id=payload.employee_id, badge_number=payload.badge_number,
        police_station=payload.police_station, department=payload.department,
        rank=payload.rank, branch=payload.branch,
    )
    db.add(user)
    await db.flush()
    verification_token = await _dispatch_email_verification(user, db)
    otp = None
    if payload.phone:
        otp = await _create_otp(db, payload.phone, "phone_verification", user)
    await _audit(db, user.id, "auth.register", request, {"role": user.role.value})
    await db.commit()
    await db.refresh(user)
    if settings.demo_mode:
        user.demo_verification_token = verification_token
        user.demo_otp = otp
    return user


@router.post("/verify-email", response_model=AuthDispatchResponse)
async def verify_email(payload: EmailVerifyRequest, request: Request, db: DB):
    try:
        claims = decode_token(payload.token, "email_verify")
        user = await db.get(User, UUID(claims["sub"]))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Verification link is invalid or expired")
    if not user or user.token_version != claims.get("ver"):
        raise HTTPException(status_code=400, detail="Verification link is invalid or expired")
    user.email_verified = True
    _activate_if_ready(user)
    await _audit(db, user.id, "auth.email_verified", request)
    await db.commit()
    return AuthDispatchResponse(message="Email verified successfully")


@router.post("/send-otp", response_model=AuthDispatchResponse)
async def send_otp(payload: OTPRequest, request: Request, db: DB):
    user = await db.scalar(select(User).where(
        (User.phone == payload.destination) | (User.email == payload.destination.lower())
    ))
    if not user:
        return AuthDispatchResponse(message="If the account exists, a verification code has been sent")
    code = await _create_otp(db, payload.destination, payload.purpose, user)
    await _audit(db, user.id, "auth.otp_sent", request, {"purpose": payload.purpose})
    await db.commit()
    return AuthDispatchResponse(
        message="Verification code sent", expires_in=OTP_MINUTES * 60,
        otp=code if settings.demo_mode else None,
    )


@router.post("/verify-otp", response_model=AuthDispatchResponse)
async def verify_otp(payload: OTPVerifyRequest, request: Request, db: DB):
    item = await _consume_otp(db, payload.destination, payload.purpose, payload.code)
    user = await db.get(User, item.user_id) if item.user_id else None
    if user and payload.purpose == "phone_verification":
        user.phone_verified = True
        _activate_if_ready(user)
    await _audit(db, user.id if user else None, "auth.otp_verified", request, {"purpose": payload.purpose})
    await db.commit()
    return AuthDispatchResponse(message="OTP verified successfully")


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, request: Request, response: Response, db: DB):
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    now = datetime.now(timezone.utc)
    if user and user.locked_until and _aware(user.locked_until) > now:
        raise HTTPException(status_code=423, detail="Account is temporarily locked after repeated failed attempts")
    valid = bool(user and verify_password(payload.password, user.hashed_password))
    if not valid:
        if user:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= LOCKOUT_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            await _audit(
                db, user.id, "auth.login_failed", request,
                {"attempts": user.failed_login_attempts, "email": payload.email.lower()},
                outcome="failure",
            )
        else:
            await _audit(
                db, None, "auth.login_failed", request,
                {"email": payload.email.lower(), "reason": "unknown_identity"},
                outcome="failure",
            )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    assert user is not None
    if user.account_status == AccountStatus.blocked:
        raise HTTPException(status_code=403, detail="Account is blocked")
    if user.account_status == AccountStatus.rejected:
        raise HTTPException(status_code=403, detail="Account registration was rejected")
    if not user.email_verified or not user.phone_verified:
        raise HTTPException(status_code=403, detail="Complete email and OTP verification before signing in")
    if user.account_status == AccountStatus.pending or not user.is_active:
        raise HTTPException(status_code=403, detail="Account is awaiting administrator approval")
    if needs_password_rehash(user.hashed_password):
        user.hashed_password = hash_password(payload.password)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    tokens = await _issue_tokens(user, db, request, remember_me=payload.remember_me)
    await _audit(db, user.id, "auth.login", request, {"session_id": str(tokens.session_id)})
    await db.commit()
    _cookie(response, tokens.refresh_token, payload.remember_me)
    return tokens


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest, request: Request, response: Response, db: DB,
    cookie_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
):
    token = payload.refresh_token or cookie_token
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token is required")
    try:
        claims = decode_token(token, "refresh")
        user_id, session_id = UUID(claims["sub"]), UUID(claims["sid"])
    except (ValueError, TypeError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    stored = await db.scalar(select(RefreshToken).where(
        RefreshToken.jti == claims.get("jti"), RefreshToken.token_hash == hash_token(token),
    ))
    user = await db.get(User, user_id)
    session = await db.get(UserSession, session_id)
    now = datetime.now(timezone.utc)
    if stored and stored.revoked_at:
        if user:
            user.token_version += 1
            for active in (await db.scalars(select(UserSession).where(
                UserSession.user_id == user.id, UserSession.revoked_at.is_(None),
            ))).all():
                active.revoked_at = now
            await db.commit()
        raise HTTPException(status_code=401, detail="Refresh token reuse detected; all sessions revoked")
    if (
        not stored or not user or not session or not user.is_active
        or user.token_version != claims.get("ver") or session.revoked_at
        or _aware(stored.expires_at) <= now or _aware(session.expires_at) <= now
    ):
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")
    stored.revoked_at = now
    tokens = await _issue_tokens(
        user, db, request, remember_me=session.remember_me, session=session,
    )
    stored.replaced_by_jti = decode_token(tokens.refresh_token, "refresh")["jti"]
    session.last_seen_at = now
    await db.commit()
    _cookie(response, tokens.refresh_token, session.remember_me)
    return tokens


@router.get("/me", response_model=UserRead)
@router.get("/profile", response_model=UserRead)
async def me(user: CurrentUser):
    return user


async def _update_profile(payload: UserUpdate, user: User, request: Request, db: AsyncSession) -> User:
    updates = payload.model_dump(exclude_unset=True)
    if "phone" in updates and updates["phone"] != user.phone:
        if updates["phone"] and await db.scalar(select(User.id).where(
            User.phone == updates["phone"], User.id != user.id,
        )):
            raise HTTPException(status_code=409, detail="Phone number is already registered")
        user.phone_verified = False
    for key, value in updates.items():
        setattr(user, key, value)
    await _audit(db, user.id, "profile.updated", request, {"fields": list(updates)})
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/me", response_model=UserRead)
async def update_me(payload: UserUpdate, request: Request, user: CurrentUser, db: DB):
    return await _update_profile(payload, user, request, db)


@router.put("/profile", response_model=UserRead)
async def update_profile(payload: UserUpdate, request: Request, user: CurrentUser, db: DB):
    return await _update_profile(payload, user, request, db)


@router.post("/change-password", response_model=Message)
async def change_password(payload: ChangePasswordRequest, request: Request, user: CurrentUser, db: DB):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    user.token_version += 1
    now = datetime.now(timezone.utc)
    for session in (await db.scalars(select(UserSession).where(
        UserSession.user_id == user.id, UserSession.revoked_at.is_(None),
    ))).all():
        session.revoked_at = now
    await _audit(db, user.id, "auth.password_changed", request)
    await db.commit()
    return Message(message="Password changed; sign in again on all devices")


@router.post("/forgot-password", response_model=AuthDispatchResponse)
async def forgot_password(payload: ForgotPasswordRequest, request: Request, db: DB):
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    code = None
    if user:
        code = await _create_otp(db, user.email, "password_reset", user)
        await _audit(db, user.id, "auth.password_reset_requested", request)
        await db.commit()
    return AuthDispatchResponse(
        message="If the account exists, a reset code has been sent",
        expires_in=OTP_MINUTES * 60, otp=code if settings.demo_mode else None,
    )


@router.post("/reset-password", response_model=Message)
async def reset_password(payload: ResetPasswordRequest, request: Request, db: DB):
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user:
        raise HTTPException(status_code=400, detail="OTP is invalid or expired")
    await _consume_otp(db, user.email, "password_reset", payload.otp)
    user.hashed_password = hash_password(payload.new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.token_version += 1
    now = datetime.now(timezone.utc)
    for session in (await db.scalars(select(UserSession).where(
        UserSession.user_id == user.id, UserSession.revoked_at.is_(None),
    ))).all():
        session.revoked_at = now
    await _audit(db, user.id, "auth.password_reset_completed", request)
    await db.commit()
    return Message(message="Password reset successfully")


@router.get("/sessions", response_model=list[SessionRead])
async def sessions(user: CurrentUser, db: DB):
    return list((await db.scalars(
        select(UserSession).where(UserSession.user_id == user.id)
        .order_by(UserSession.last_seen_at.desc()).limit(100)
    )).all())


@router.post("/logout", response_model=Message)
async def logout(
    request: Request, response: Response, user: CurrentUser, db: DB,
):
    try:
        claims = decode_token(request.headers.get("authorization", "").removeprefix("Bearer "))
        session_id = UUID(claims["sid"]) if claims.get("sid") else None
    except (ValueError, TypeError):
        session_id = None
    if session_id:
        session = await db.get(UserSession, session_id)
        if session and session.user_id == user.id:
            session.revoked_at = datetime.now(timezone.utc)
    else:
        user.token_version += 1
    await _audit(db, user.id, "auth.logout", request)
    await db.commit()
    response.delete_cookie(REFRESH_COOKIE, path="/auth")
    return Message(message="Session ended")


@router.post("/logout-all", response_model=Message)
async def logout_all(request: Request, response: Response, user: CurrentUser, db: DB):
    user.token_version += 1
    now = datetime.now(timezone.utc)
    for session in (await db.scalars(select(UserSession).where(
        UserSession.user_id == user.id, UserSession.revoked_at.is_(None),
    ))).all():
        session.revoked_at = now
    await _audit(db, user.id, "auth.logout_all", request)
    await db.commit()
    response.delete_cookie(REFRESH_COOKIE, path="/auth")
    return Message(message="All devices signed out")


@router.delete("/account", response_model=Message)
async def delete_account(payload: AccountDeleteRequest, request: Request, user: CurrentUser, db: DB):
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Password is incorrect")
    user.account_status = AccountStatus.blocked
    user.is_active = False
    user.token_version += 1
    await _audit(db, user.id, "auth.account_deactivated", request)
    await db.commit()
    return Message(message="Account deactivated")


@router.get("/permissions")
async def permissions(user: CurrentUser, db: DB):
    if user.role == UserRole.administrator:
        items = list((await db.scalars(select(Permission.code))).all())
    else:
        items = list((await db.scalars(select(RolePermission.permission_code).where(
            RolePermission.role_name == user.role.value,
        ))).all())
    return {"role": user.role, "permissions": items}


@router.get("/admin/users", response_model=list[UserRead])
async def admin_users(
    admin: AdminUser, db: DB, account_status: AccountStatus | None = None,
):
    statement = select(User)
    if account_status:
        statement = statement.where(User.account_status == account_status)
    return list((await db.scalars(statement.order_by(User.created_at.desc()).limit(500))).all())


@router.post("/admin/users/{user_id}/action", response_model=UserRead)
async def admin_user_action(
    user_id: UUID, payload: AdminAccountAction, request: Request, admin: AdminUser, db: DB,
):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id and payload.action in {"block", "reject", "delete"}:
        raise HTTPException(status_code=400, detail="Administrators cannot disable their own account")
    now = datetime.now(timezone.utc)
    if payload.action == "approve":
        if not target.email_verified or not target.phone_verified:
            raise HTTPException(status_code=400, detail="Email and phone must be verified before approval")
        target.account_status, target.is_active = AccountStatus.verified, True
        target.approved_by, target.approved_at = admin.id, now
    elif payload.action == "reject":
        target.account_status, target.is_active = AccountStatus.rejected, False
    elif payload.action == "block":
        target.account_status, target.is_active = AccountStatus.blocked, False
        target.token_version += 1
    elif payload.action == "unblock":
        target.account_status, target.is_active = AccountStatus.verified, True
    else:
        target.account_status, target.is_active = AccountStatus.blocked, False
        target.token_version += 1
    await _audit(db, admin.id, f"admin.user_{payload.action}", request, {
        "target_user_id": str(target.id), "reason": payload.reason,
    })
    await db.commit()
    await db.refresh(target)
    return target


@router.put("/admin/users/{user_id}/role", response_model=UserRead)
async def assign_role(
    user_id: UUID, payload: AssignRoleRequest, request: Request, admin: AdminUser, db: DB,
):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.role = payload.role
    await _audit(db, admin.id, "admin.role_assigned", request, {
        "target_user_id": str(target.id), "role": payload.role.value,
    })
    await db.commit()
    await db.refresh(target)
    return target


@router.get("/admin/login-history")
async def login_history(admin: AdminUser, db: DB):
    items = list((await db.scalars(select(AuditLog).where(
        AuditLog.action.in_(("auth.login", "auth.login_failed")),
    ).order_by(AuditLog.created_at.desc()).limit(500))).all())
    return {"items": [{
        "id": str(item.id), "user_id": str(item.user_id) if item.user_id else None,
        "action": item.action, "status": item.status, "ip_address": item.ip_address,
        "details": item.details, "created_at": item.created_at,
    } for item in items]}


@router.get("/admin/audit-logs")
async def audit_logs(
    admin: AdminUser, db: DB,
    action: str | None = None,
    outcome: str | None = Query(None, alias="status"),
    limit: int = Query(200, ge=1, le=1000),
):
    filters = []
    if action:
        filters.append(AuditLog.action.ilike(f"%{action}%"))
    if outcome:
        filters.append(AuditLog.status == outcome)
    items = list((await db.scalars(
        select(AuditLog).where(*filters).order_by(AuditLog.created_at.desc()).limit(limit)
    )).all())
    user_ids = {item.user_id for item in items if item.user_id}
    users = {
        user.id: user
        for user in (await db.scalars(select(User).where(User.id.in_(user_ids)))).all()
    } if user_ids else {}
    return {"items": [{
        "id": str(item.id),
        "user_id": str(item.user_id) if item.user_id else None,
        "user": users[item.user_id].full_name if item.user_id in users else item.details.get("email", "Unknown user"),
        "email": users[item.user_id].email if item.user_id in users else item.details.get("email"),
        "action": item.action,
        "resource": item.resource,
        "resource_id": item.resource_id,
        "timestamp": item.created_at,
        "ip_address": item.ip_address,
        "status": item.status,
        "details": item.details,
    } for item in items]}
