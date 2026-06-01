from typing import Any

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class LoginRequest(BaseModel):
    username: str
    password: str


class HistoryResponse(BaseModel):
    history: dict[str, Any]
