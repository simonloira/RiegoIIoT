from datetime import datetime
from json import load
from os import getcwd

from backend.clima.models import (
    AemetData,
    CurrentWeatherData,
    MeteoGaliciaData,
)

PATH = getcwd()


def is_night(current_hour: int, sunriset_time: str, sunset_time: str) -> bool:
    sunrise_h = int(sunriset_time.split(":")[0])
    sunset_h = int(sunset_time.split(":")[0])

    if current_hour >= sunrise_h and current_hour <= sunset_h:
        return False
    return True


def get_day_hour_index(aemet_h: AemetData) -> tuple[int, int]:
    now = datetime.now()
    hour_index: int = 0
    day_index: int = 0

    for day_index, day in enumerate(aemet_h.days):
        if day.date is None:
            continue
        date = day.date.split("-")

        first_hour = day.sky_status[0].hour
        last_hour = day.sky_status[-1].hour
        if first_hour is None or last_hour is None:
            continue

        max_index = int(last_hour) - int(first_hour)
        current_index: int = now.hour - int(first_hour)
        hour_index = int(min(current_index, max_index))

        if (
            now.year == int(date[0])
            and now.month == int(date[1])
            and now.day == int(date[2])
        ):
            return day_index, hour_index

    return day_index, hour_index


def current_data(
    aemet_h: AemetData, meteogalicia: MeteoGaliciaData
) -> CurrentWeatherData:
    # Los datos de aemet se componen de la sigueinte manera:
    # Es un diccionario con unas keys, dentro de esas keys existe la key "dia"
    # que es una lista de diccionarios cada elemento de esa lista representa la
    # información climatológica de cada día "dia"[0] (hoy) "dia"[1] mañana, etc
    # Cada diccionario de cada dái tiene unas keys dentro de esas keys está la
    # key "estado_cielo" que es una lista de diccionarios cada diccionario
    # tiene las keys ["@periodo"(hora), "@descripcion"(estado del cielo),
    # "#text"(nombre icono)]

    day_index, hour_index = get_day_hour_index(aemet_h)

    # Hora actual - primera hora de los datos de day_index Por ejemplo: Igual
    # la primera hora son las 00 o igual son las 9 pero aemet siempre hace los
    # informes antes de la hora actual o justo a la hora actual. Que me lleguen
    # informes hechos después de la hora actual es físicamente imposible
    # (todavía no se inventaron los viajes al futuro) y si aemet hace el
    # informe tipo a las 9:42 la primera hora del day_index = 0 serían las 9:42
    # si day_index es 1 la primera hora serían las 00:00 porque sería el día
    # siguiente.

    temperature = int(meteogalicia.temp_15m)
    dew_point = int(meteogalicia.temp_dewpoint)
    status = aemet_h.days[day_index].sky_status[hour_index].description or ""
    sunrise = aemet_h.days[0].sunrise or ""
    sunset = aemet_h.days[0].sunset or ""

    night = is_night(hour_index, sunrise, sunset)
    if night:
        status += " noche"

    with open(
        f"{PATH}/frontend/static/weather_icons/icons.json", encoding="UTF-8"
    ) as file:
        icon: str = load(file)[status]

    return CurrentWeatherData(
        index_day=day_index,
        index_hour=hour_index,
        sky_status=status,
        sky_icon=icon,
        temperature=temperature,
        dew_point=dew_point,
    )
