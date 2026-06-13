from dataclasses import dataclass
from enum import Enum
from logging import getLogger
from time import time
from typing import Literal, TypedDict

from pydantic import BaseModel

logger = getLogger(__name__)

type AemetFullData = dict[Literal['7d', 'hourly'], AemetData]

type AllMagnitudeVariants = None | list[MagnitudData] | MagnitudData | str
type RawAemetData = dict[str, dict[str, AemetPrediction | str]]
type AemetPrediction = dict[str, list[DayData]]
type DayData = dict[str, str | list[MagnitudData]]
type MagnitudData = dict[str, str] | str


@dataclass
class MeteoGaliciaData:
    timestamp: str
    station_id: str
    temp_15m: float = 0.0
    temp_dewpoint: float = 0.0
    hum_rel: float = 0.0
    last_rain: float = 0.0
    accum_rain: float = 0.0
    wind_speed: float = 0.0
    wind_gust: float = 0.0
    wind_dir: float = 0.0
    wind_gust_dir: float = 0.0
    solar_radiation: float = 0.0
    solar_hours: float = 0.0


class WeatherData(TypedDict, total=False):
    meteogalicia: MeteoGaliciaData
    aemet: AemetFullData


class APIs(Enum):
    METEOGALICIA = 'meteogalicia'
    AEMET = 'aemet'


class AemetMagnitud(BaseModel):
    hour: str | None
    value: str | None
    description: str | None

class AemetDayBase(BaseModel):
    date: str | None
    sunrise: str | None
    sunset:str | None
    uv_max: str | None
    max_temp:str | None
    min_temp: str | None
    temperature: list[AemetMagnitud]
    sky_status: list[AemetMagnitud]
    rain: list[AemetMagnitud]
    therm_sense: list[AemetMagnitud] | None

class AemetData(BaseModel):
    made_date: str
    village: str
    province:str
    days: list[AemetDayBase]


class CurrentWeatherData(BaseModel):
    index_day:int
    index_hour:int
    sky_status:str
    sky_icon:str
    temperature:int
    dew_point:int


@dataclass
class APIState:
    """Estado de las llamadas a la API"""

    last_fetch_time: float = 0
    next_retry_time: float = 0

    def __can_fetch(self, cache_ttl: int) -> bool:
        """Verificar si se puede hacer una nueva petición"""
        can_fetch = (time() - self.last_fetch_time) > cache_ttl
        logger.debug(f"TTL:{cache_ttl} Last fecthed: {self.last_fetch_time}")
        logger.debug(f"Puede llamar? {can_fetch}")
        return can_fetch

    def __can_retry(self) -> bool:
        """Verificar si se puede reintentar"""
        can_retry = self.next_retry_time > 0 and time() > self.next_retry_time
        logger.debug(f"ts-Reintento:{self.next_retry_time} ts-ahora: {time()}")
        logger.debug(f"Puede reintentar? {can_retry}")
        return can_retry

    def can_call_or_retry(self, cache_ttl: int) -> bool:
        return self.__can_fetch(cache_ttl) or self.__can_retry()


# Diccionario de mapeo: idParam -> nombre_columna_dataclass
MAP_SIMPLE = {
    83: "temp_15m",
    10018: "temp_dewpoint",
    86: "hum_rel",
    10001: "last_rain",
    88: "solar_radiation",
    10006: "solar_hours"
}

# Mapeo para el viento (mismo idParam, distinta idFunction)
MAP_COMPLEX = {
    (81, 1): "wind_speed",
    (81, 14): "wind_gust",
    (82, 1): "wind_dir",
    (82, 15): "wind_gust_dir"
}
