
from asyncio import Task
from dataclasses import dataclass
from typing import Literal, Annotated

from pydantic import BaseModel, Field, RootModel
from enum import Enum

type PLCVirtualMemory = dict[TagName, PLCVariableAddress]
type PLCVariableAddress = Annotated[
    PLCTimer | WeeklyTimer | AstroClock,
    Field(discriminator="type")
]
type TagName = str

type PLCAddress = tuple[int, int] #[byte, bit]
type Buffer = list[list[bool]]

class MemoryBlock(BaseModel):
    memory_index: int
    length: Literal['byte', 'word', 'dword']


class ZonesMemories(BaseModel):
    local_act:dict[TagName, PLCAddress] = Field(...,
                                                alias="DIRECCIONES_ACT_LOCAL_PLC")
    web_control:dict[TagName, PLCAddress] = Field(...,
                                                  alias="DIRECCIONES_CONTROL_WEB")
    outputs:dict[TagName, PLCAddress] = Field(...,
                                              alias="DIRECCIONES_SALIDAS")


class VirtualMemories(RootModel[PLCVirtualMemory]):
    pass

class PLCTimer(BaseModel):
    type: Literal['timer']
    time: MemoryBlock
    timebase: MemoryBlock

@dataclass(slots=True)
class WeeklySlot:
    weekday: MemoryBlock
    ontime:MemoryBlock
    offtime:MemoryBlock

class WeeklyTimer(BaseModel):
    type: Literal['weekly']
    slots: list[WeeklySlot]

class AstroClock(BaseModel):
    type: Literal['astroclock']
    sunrise_offset:MemoryBlock


@dataclass(slots=True)
class ZoneActivationInfo:
    event:Literal['start', 'manual_stop']
    msg: str
    duration: int
    zone: str


@dataclass(slots=True)
class ActivationTask:
    start_time:float
    task:Task[None]


@dataclass(slots=True)
class LocalMemoriesStatus:
    act_flags: list[TagName] | None
    deact_flags: list[TagName] | None


class BasesTime(Enum):
    HOUR = 3
    MINUTES = 2
    SECONDS = 1
