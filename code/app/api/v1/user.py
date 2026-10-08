from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession
from app.core.config import settings
from app.core.response import ok
from app.core.security import decode_access_token, extract_bearer_token
from app.services import auth_service, sms_service

router = APIRouter(prefix="/user", tags=["user"])


class SmsCodeRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=11)


class RegisterRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=11)
    code: str = Field(min_length=6, max_length=6)
    agreement: bool


class LoginRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=11)
    code: str = Field(min_length=6, max_length=6)


@router.post("/sms-code")
async def send_sms_code(payload: SmsCodeRequest) -> dict:
    await sms_service.send_sms_code(payload.phone)
    return ok({"sent": True})


@router.post("/register")
async def register(payload: RegisterRequest, db: DbSession) -> dict:
    user = await auth_service.register(db, payload.phone, payload.code, payload.agreement)
    return ok({"user_id": user.id, "phone": user.phone})


@router.post("/login")
async def login(payload: LoginRequest, db: DbSession) -> dict:
    result = await auth_service.login(db, payload.phone, payload.code)
    return ok(result)


@router.post("/logout")
async def logout(authorization: Annotated[str | None, Header()] = None) -> dict:
    token = extract_bearer_token(authorization)
    payload = decode_access_token(token, settings.jwt_secret)
    await auth_service.logout(token, payload.expires_at)
    return ok({"logged_out": True})
