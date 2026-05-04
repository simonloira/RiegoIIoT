from dataclasses import dataclass
from time import time

@dataclass
class MeteoGaliciaData:
    timestamp: str 
    station_id: int
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


@dataclass
class APIState:
    """Estado de las llamadas a la API"""
    last_fetch_time: float = 0
    next_retry_time: float = 0

    def __can_fetch(self, cache_ttl: int) -> bool:
        """Verificar si se puede hacer una nueva petición"""
        print(cache_ttl, self.last_fetch_time)
        print(f"Puede llamar? {(time() - self.last_fetch_time) > cache_ttl}")
        return (time() - self.last_fetch_time) > cache_ttl
    
    def __can_retry(self) -> bool:
        """Verificar si se puede reintentar"""
        print(self.next_retry_time, time())
        print(f"Puede reintentar? {self.next_retry_time > 0 and time() > self.next_retry_time }")
        return self.next_retry_time > 0 and time() > self.next_retry_time 
    
    def can_call_or_retry(self, cache_ttl: int):
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