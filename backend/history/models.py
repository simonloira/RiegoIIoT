from typing import Literal

from pydantic import BaseModel

type ClientIP = str
type ZoneName = str
type UserEvents = Literal['connected', 'disconnected']
type PLCEvents = Literal['start', 'manual_stop', 'stop']
type LastActivation = ZoneActivation | None

class UserConnected(BaseModel):
    ip: str
    event: UserEvents
    timestamp: int
    name: str


class ZoneActivation(BaseModel):
    event: PLCEvents
    timestamp: int
    duration: int
    zone: str


class History(BaseModel):
    #Users no es una lista para que se sobrescriba el estado del cliente
    users: dict[ClientIP, UserConnected] = {}
    plc: dict[ZoneName, list[ZoneActivation]] = {}
    last_activation: LastActivation = None
