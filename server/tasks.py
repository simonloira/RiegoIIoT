import asyncio
from random import randint
from time import time

from backend.clima.climate_flags import get_day_hour_index
from backend.clima.models import AemetFullData, MeteoGaliciaData
from backend.clima.weather_manager import WeatherExtractor
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
            meteogalicia = weather_data.get("meteogalicia")
            aemet = weather_data.get("aemet")
            if meteogalicia is None or aemet is None:
                await asyncio.sleep(60)
                continue
            print("tasks.py: ", weather_data)
            print("check_rain")
            rain_expected: bool = check_rain(meteogalicia, aemet)
            plc.write_raining_memorie(rain=rain_expected)
            print("✅ Datos del clima actualizados.")
        except KeyError as e:
            print("❌ Error al actualizar clima:", e)
        # Entre cada 20 y 40 minutos se actualiza la información
        await asyncio.sleep(randint(20, 40) * 60)


def check_rain(
    meteogal_data: MeteoGaliciaData, aemet_data: AemetFullData
) -> bool:
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
    print("A ver si se prevé lluvia. Si se activa M18 es que sí que lloverá.")

    try:
        index_day, hour_index = get_day_hour_index(aemet_data["hourly"])

        if meteogal_data.accum_rain >= 5:
            print("Meteogalicia dice que llueve")
            return True
        print("Meteogalicia dice que nada, no llueve")
        # Se comprueba si en algún momento del día lloverá
        aemet_h = aemet_data["hourly"].days[index_day].rain
        for period in aemet_h[hour_index:]:
            value = period.value
            if value == "Ip" or value is None:
                continue

            if float(value) > 0.2:
                print("Aemet_hourly dice que llueve")
                return True
        print("Aemet_hourly dice que nada, no llueve")
        # En el caso de que la predicción por horas no ponga que va a llover,
        # se comprueba en la predicción del día completo
        aemet_7d = aemet_data["7d"].days[index_day].rain
        for period in aemet_7d:
            value = period.value
            if value == "Ip" or value is None:
                continue
            # Entero porque los porcentajes siempre se representan de 0-100 en
            # enteros: Si hay una probabilidad mayor al 40% se considera que
            # lloverá
            if int(value) >= 100:
                print("Aemet_7d dice que llueve")
                return True

        print("No llueve vamos!!")
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
