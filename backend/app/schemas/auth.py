import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import AccountStatus, UserRole


def _strong_password(value: str) -> str:
    if not (
        len(value) >= 10 and re.search(r"[A-Z]", value) and re.search(r"[a-z]", value)
        and re.search(r"\d", value) and re.search(r"[^A-Za-z0-9]", value)
    ):
        raise ValueError("Password must contain uppercase, lowercase, number, and special character")
    return value


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=150)
    phone: str | None = Field(default=None, min_length=8, max_length=20)
    password: str = Field(min_length=10, max_length=128)
    confirm_password: str | None = Field(default=None, min_length=10, max_length=128)
    role: UserRole = UserRole.citizen
    state: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    preferred_language: str = Field(default="English", max_length=30)
    organization: str | None = Field(default=None, max_length=180)
    employee_id: str | None = Field(default=None, max_length=80)
    badge_number: str | None = Field(default=None, max_length=80)
    police_station: str | None = Field(default=None, max_length=180)
    department: str | None = Field(default=None, max_length=150)
    rank: str | None = Field(default=None, max_length=100)
    branch: str | None = Field(default=None, max_length=180)
    accept_terms: bool = True

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return _strong_password(value)

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if not value:
            return value
        normalized = re.sub(r"[\s()-]", "", value)
        digits = normalized[1:] if normalized.startswith("+") else normalized
        if not digits.isdigit() or not 8 <= len(digits) <= 15:
            raise ValueError("Enter a valid phone number")
        return normalized

    @model_validator(mode="after")
    def validate_registration(self):
        if self.confirm_password is not None and self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        if not self.accept_terms:
            raise ValueError("Terms must be accepted")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    session_id: UUID | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    full_name: str
    phone: str | None
    role: UserRole
    account_status: AccountStatus
    is_active: bool
    email_verified: bool
    phone_verified: bool
    state: str | None
    district: str | None
    preferred_language: str
    organization: str | None
    employee_id: str | None
    badge_number: str | None
    police_station: str | None
    department: str | None
    rank: str | None
    branch: str | None
    profile_picture: str | None
    notification_preferences: dict[str, Any]
    created_at: datetime
    last_login_at: datetime | None
    demo_verification_token: str | None = None
    demo_otp: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, min_length=8, max_length=20)
    preferred_language: str | None = Field(default=None, max_length=30)
    state: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    profile_picture: str | None = Field(default=None, max_length=500)
    notification_preferences: dict[str, bool] | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return _strong_password(value)


class OTPRequest(BaseModel):
    destination: str = Field(min_length=3, max_length=320)
    purpose: Literal["phone_verification", "password_reset"] = "phone_verification"


class OTPVerifyRequest(BaseModel):
    destination: str = Field(min_length=3, max_length=320)
    code: str = Field(pattern=r"^\d{6}$")
    purpose: Literal["phone_verification", "password_reset"] = "phone_verification"


class EmailVerifyRequest(BaseModel):
    token: str = Field(min_length=20, max_length=500)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$")
    new_password: str = Field(min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return _strong_password(value)


class AccountDeleteRequest(BaseModel):
    password: str


class AdminAccountAction(BaseModel):
    action: Literal["approve", "reject", "block", "unblock", "delete"]
    reason: str | None = Field(default=None, max_length=1000)


class AssignRoleRequest(BaseModel):
    role: UserRole


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ip_address: str | None
    user_agent: str | None
    device_name: str | None
    remember_me: bool
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class AuthDispatchResponse(BaseModel):
    message: str
    expires_in: int | None = None
    verification_token: str | None = None
    otp: str | None = None
