import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def normalize_phone_number(value: str) -> str:
    normalized = re.sub(r"[\s()-]", "", value)
    if re.fullmatch(r"05\d{9}", normalized):
        return f"+90{normalized[1:]}"
    if re.fullmatch(r"\+905\d{9}", normalized):
        return normalized
    raise ValueError("GSM numarasını 05XXXXXXXXX veya +905XXXXXXXXX biçiminde girin.")


class PhoneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone_number: str = Field(min_length=10, max_length=16)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        return normalize_phone_number(value)


class VerifyOtpRequest(PhoneRequest):
    otp: str = Field(pattern=r"^\d{4}$")


class OtpRequestResponse(BaseModel):
    message: str
    simulation_code: str
    expires_in_seconds: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone_number: str
    first_name: str
    last_name: str
    email: str | None
    role: Literal["CUSTOMER", "SHOP_OWNER", "ADMIN"]
    preferences: dict[str, list[str]] | None
    profile_completed: bool


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class ProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    email: str | None = Field(default=None, max_length=255)
    coffee_preferences: list[str] | None = None
    allergens: list[str] | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None and value.strip():
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
                raise ValueError("Geçerli bir e-posta adresi girin.")
            return value.strip()
        return None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "ProfileUpdate":
        if not self.model_fields_set:
            raise ValueError("Güncellenecek en az bir alan gönderin.")
        return self


class RoleChangeRequest(BaseModel):
    role: Literal["CUSTOMER", "SHOP_OWNER"]
