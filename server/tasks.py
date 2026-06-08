import asyncio
from random import randint
from time import time

from backend.clima.climate_flags import get_day_hour_index
from backend.clima.models import AemetFullData
from backend.clima.weather_manager import WeatherExtractor
from backend.crud.utils import get_accumulated_rain_grass
from backend.history.history_manager import HistorySave
from backend.history.models import ZoneActivation
from backend.PLC.plc_manager import PLCControl


async def automatic_get_weather(
    plc: PLCControl, weather_extractor: WeatherExtractor
) -> None:
    while True:
        try:
            print("☁️ Actualizando datos climatológicos...")
            weather_data = weather_extractor.get_weather_data()
            aemet = weather_data.get("aemet")
            if aemet is None:
                await asyncio.sleep(60)
                continue
            print("tasks.py: ", weather_data)
            print("\nComprobando si hace falta regar:")
            irrigate: bool = check_if_irrigate(aemet)
            print(f"¿Hace falta regar? {irrigate}")
            
            plc.write_irrigate_memorie(irrigate)
            print("✅ Datos del clima actualizados.")
        except KeyError as e:
            print("❌ Error al actualizar clima:", e)
        # Entre cada 20 y 40 minutos se actualiza la información
        await asyncio.sleep(randint(20, 40) * 60)


def check_if_irrigate(aemet: AemetFullData) -> bool:
    # No es una decisión final. Es una decisión actual basada
    # en el momento en el que se están haciendo las comprobaciones
    # puede ser que en otra comprobación se decida que es necesario regar
    # pero el PLC sólo deja regar 1 sóla vez
    accum_grass_rain = get_accumulated_rain_grass()
    if accum_grass_rain is None:
        # Como noy hay información lo paso a 0. El None me sirve
        # para mandar una advertencia al frontend o así
        accum_grass_rain = 0

    index_day, hour_index = get_day_hour_index(aemet["hourly"])
    enough_rain = check_rain(accum_grass_rain, aemet, index_day, hour_index)

    if enough_rain:
        return False #No riega, llovió suficiente

    period = aemet["hourly"].days[index_day].rain[hour_index]
    if period.value is None:
        return True  # No sé si lloverá o no así que por si acaso, riego ya

    if float(period.value) == 0.0:
        return True  # Ahora mismo no va a llover así que se riega ya
    
    return False


def check_rain(accum_grass_rain: float, 
               aemet_data: AemetFullData, 
               index_day: int, 
               hour_index: int) -> bool:
    # weather_data = [[aemet_7d, aemet_h], [meteogal]]
    # Hour_index es el índice del periodo que representa la hora actual.
    # Por defecto sería 0, si index_day es 1 es que el informe de los datos de
    # aemet se hizo el día anterior, o sea lo más seguro es que si day_index es
    # 1 es que, en ese momento, es de madrugada porque aún no actualizaron los
    # datos los de aemet. Sabiendo esto, si lo dejo en 0 siempre se rompe el
    # código, o en su defecto, no muestra la información actual.
    # Entonces con index_hour pasa algo similar porque los datos de aemet_h no
    # empiezan en las 00, empiezan en la hora en la que se hizo el informe.
    #
    # Ejemplo:
    # Si hoy es 28/10/2025 y el informe se hizo a las 15:32 -> index_day es 0 |
    # la primera hora de aemet_h es 15 (aemet_h.days[0].rain[0].hour = 15).
    # Entonces, el bucle for que busca en aemet_h lo que hace es obviar todos
    # los periodos anteriores y empieza en el elemento que está en la posición
    # igual a hour_index (for period in **aemet_h[hour_index:]**:)
    estimated_rain: float = accum_grass_rain
    RAIN_THRESHOLD = 5  # Unidad en mm o l/m^2
    try:
        if accum_grass_rain >= RAIN_THRESHOLD:
            print("Entre ayer y la hora de riego llovió lo sufiente.")
            return True
        print("No llovió lo suficiente. ¿Se alcanzará a lo largo del día?")
        
        # Se calcula cuánto loverá a lo largo del día
        aemet_h = aemet_data["hourly"].days[index_day].rain
        for period in aemet_h[hour_index:]:
            value = period.value
            if value == "Ip" or value is None:
                continue
            estimated_rain += float(value)
            if estimated_rain > RAIN_THRESHOLD:
                print(f"Aemet_hourly. Lloverá sufiente: {estimated_rain}mm")
                return True

        print(f"Parece que va a hacer falta regar: {estimated_rain}mm")
        return False
    except Exception as e:
        print(f"Error comprobando si lloverá: {e}")
        return False


async def server_heartbeat(plc: PLCControl) -> None:
    # Se escribe en la marca M19 para que el LOGO sepa que el servidor sigue
    # "vivo", es decir, que no está caído. Se enciende y se apaga cada dos
    # segundos porque en el programa del LOGO hay dos temporizadores que si
    # pasan 5 segundos sin haber cambios detectan que se detuvo el "latido",
    # del servidor por lo que está caído, y pasa al modo de riego programado.
    while True:
        await asyncio.sleep(2)
        plc.plc_client.write_memory(
            (2, 2), True if plc.plc_client.is_connected() else False
        )
        await asyncio.sleep(2)
        plc.plc_client.write_memory(
            (2, 2), False if plc.plc_client.is_connected() else False
        )


async def plc_reconnection(plc: PLCControl) -> None:
    while True:
        plc.plc_client.plc_reconnection()
        await asyncio.sleep(4)


async def plc_watchdog(plc: PLCControl, history_handler: HistorySave) -> None:
    """Lee las marcas de memoria que tuvieron un flanco de bajada o de subida,
    con su nombre descriptivo. Se iteran y se guarda su estado en el historial.

    Args:
        plc (PLCControl): Variable que contiene el objeto PLCControl
         inicializado.
        history_handler (HistorySave): Variable que permite guardar el
         historial inicializado.
    """
    while True:
        result = plc.get_local_active_memories()
        act_flags = result.act_flags
        deact_flags = result.deact_flags
        # Realmente sólo devuelve None si el buffer de memorias es None.
        # Por lo tanto si act_flags es None deact_flags también. Lo que
        # pasa es que pongo OR en vez de AND porque sino mypy se piensa que
        # alguno de los dos puede ser None
        if act_flags is None or deact_flags is None:
            # Espero un poco más por si hay algún problema de comunicación que
            # no trate de leer las memorias contantemente.
            await asyncio.sleep(5)
            continue

        for flag in act_flags:
            history_handler.save_output_status(
                info=ZoneActivation(
                    event="local_start",
                    timestamp=int(time()),
                    zone=flag
                )
            )

        for flag in deact_flags:
            history_handler.save_output_status(
                info=ZoneActivation(
                    event="local_stop",
                    timestamp=int(time()),
                    zone=flag
                )
            )

        await asyncio.sleep(2)  # Cada 2 segundos leo el estado de las memorias
