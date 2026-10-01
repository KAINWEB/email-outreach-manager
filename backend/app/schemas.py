from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SenderAccountCreate(BaseModel):
    email: EmailStr
    sender_name: str = ""
    provider: str = "mock"
    daily_limit: int = Field(default=50, ge=1, le=100000)
    rate_limit_per_minute: int = Field(default=10, ge=1, le=10000)


class SenderAccountUpdate(BaseModel):
    sender_name: str | None = None
    enabled: bool | None = None
    daily_limit: int | None = Field(default=None, ge=1, le=100000)
    rate_limit_per_minute: int | None = Field(default=None, ge=1, le=10000)


class SenderAccountOut(ORMModel):
    id: int
    email: str
    sender_name: str
    provider: str
    enabled: bool
    connection_status: str
    daily_limit: int
    rate_limit_per_minute: int
    sent_today: int
    sent_today_date: str
    last_error: str | None


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class CampaignOut(ORMModel):
    id: int
    name: str
    status: str
    source_filename: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class MappingRequest(BaseModel):
    mapping: dict[str, str]


class RecipientUpdate(BaseModel):
    email: EmailStr | None = None
    company: str | None = None
    name: str | None = None
    subject: str | None = None
    message: str | None = None
    sender_account_id: int | None = None


class RecipientOut(ORMModel):
    id: int
    campaign_id: int
    row_number: int
    email: str
    company: str
    name: str
    subject: str
    message: str
    status: str
    validation_error: str | None
    is_duplicate: bool
    sender_account_id: int | None


class LaunchRequest(BaseModel):
    sender_account_ids: list[int]
    test_mode: bool = False
    test_addresses: list[EmailStr] = []
    confirmed: bool = False


class SuppressionCreate(BaseModel):
    email: EmailStr
    reason: str = "manual"
