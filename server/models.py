from typing import Any, Literal

from pydantic import BaseModel

from backend.history.models import LastActivation, History
from backend.PLC.models import PLCAddress, TagName
from backend.clima.models import MeteoGaliciaData, AemetFullData, CurrentWeatherData

class MessageResponse(BaseModel):
    message: str


class LoginRequest(BaseModel):
    username: str
    password: str


class HistoryResponse(BaseModel):
    history: History


class SocketRequest(BaseModel):
    command: Literal["activate-zone", "change-zone-time"]
    zone: str
    act_time: int


class SocketResponse(BaseModel):
    event: str
    status: Literal["success", "error"]
    error_msg: str | None = None

class SocketMessageResponse(SocketResponse):
    data: dict[str, Any] = {}
    broadcast: bool

class PLCDataResponse(SocketResponse):
    plc_connected: bool
    status_memories: dict[str, bool|None] | None = None
    outputs: list[bool] | None = None
    outputs_addresses: dict[TagName, PLCAddress]
    last_activation: LastActivation = None


class WeatherResponse(CurrentWeatherData):
    meteogalicia: MeteoGaliciaData
    aemet:AemetFullData