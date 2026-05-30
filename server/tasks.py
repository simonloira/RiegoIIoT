import asyncio
from random import randint

from backend.clima.climate_flags import get_day_hour_index
import backend.PLC.plc_manager as plc_manager
import backend.clima.weather_manager as weather_manager


async def automatic_get_weather():
    while True:
        try:
            print("☁️ Actualizando datos climatológicos...")
            weather = weather_manager.get_weather.get_weather_data()
            print("tasks.py: ", weather)
            print("check_rain")
            rain_expected = check_rain(weather_data=weather)
            plc_manager.plc.write_raining_memorie(rain=rain_expected)
            print("✅ Datos del clima actualizados.")
        except Exception as e:
            print("❌ Error al actualizar clima:", e)
        await asyncio.sleep(randint(20, 40) * 60)  # Entre 20 y 40 minutos se actualiza la información


def check_rain(weather_data):
    #weather_data = [[aemet_7d, aemet_h], [meteogal]]
    # Hour_index es la hora actual.
    # Para entenderlo mejor hay que verse los datos de aemet_h y aemet_7d. O sea index_day será el día actual. Por defecto sería 0, si index_day es 1 es que el informe 
    # de los datos de aemet se hizo el día anterior, o sea lo más seguro es que si day_index es 1 es que, en ese momento, es de madrugada porque aún no actualizaron los datos los de aemet; 
    # pero si lo dejo en 0 siempre, se rompe el código; o en su defecto, no muestra la información actual. Entonces con index_hour pasa algo similar porque los datos de aemet_h no empiezan 
    # en las 00, empiezan en la hora en la que se hizo el informe. 
    # Ejemplo:
    # Si hoy es 28/10/2025 y el informe se hizo a las 15:32 -> index_day es 0 | la primera hora de aemet_h (aemet_h["dia"][index_day=0]["precipitacion"][hour_index]) es igual a 15
    # Entonces el bucle for que busca en aemet_h hace esto: i empieza siendo 0, aemet_h["dia"][index_day]["precipitacion"] tendría 9 elementos ya que 24-15 = 9 (24h que tiene un día)
    # Primera iteración: hour_index(15) + i(0) = 15
    # Segunda iteración: hour_index(15) + i(1) = 16
    # ... Última iteración: hour_index(15) + i(9 = len(aemet_h)) = 24

    print("A ver si se prevé lluvia. Si se activa M18 es que sí que lloverá.")
    
    try:
        index_day, hour_index = get_day_hour_index(weather_data[0][1]) #weather_data = [[aemet_7d, aemet_h], [meteogal]]
        
        meteogalicia = weather_data[1][0]["Precipitación"][1]
        if meteogalicia >= 0.1:
            return True

        #Se comprueba si en algún momento del día llovió o lloverá
        aemet_h = weather_data[0][1]["dia"][index_day]["precipitacion"]
        for i in range(len(aemet_h)-1):
            # if float(aemet_h[hour_index+i]["#text"]) > 0:
            if aemet_h[i]["#text"] == "Ip":
                continue
            if float(aemet_h[i]["#text"]) > 0.2:
                return True

        #En el caso de que la predicción por horas no ponga que va a llover, se comprueba en la predicción del día completo
        aemet_7d = weather_data[0][0]["dia"][index_day]["prob_precipitacion"]
        for period in aemet_7d[4:]: #Se saltan 4 periodos porque no valen para nada y dan errores
            if not "#text" in period.keys(): #Si period no contiene #text es que no hay un valor de probabilidad de lluvia
                continue
            if period["#text"] is None or period["#text"] == "Ip":
                continue
            if int(period["#text"]) > 40: #Entero porque los porcentajes siempre se representan de 0-100 en enteros: Si hay una probabilidad mayor al 40% se considera que lloverá
                return True
        
        print("No llueve vamos!!")
        return False
    except Exception as e:
        print(f"Error {e}")


async def server_heartbeat():
    while True:
        await asyncio.sleep(2)
        plc_manager.plc.plc_client.write_memories([2,2], True, show_status=False if plc_manager.plc.plc_client.is_connected() else False) #Escribir en M19 (marca que se muestra en la pantalla del LOGO, que está conectado al servidor)
        await asyncio.sleep(2)
        plc_manager.plc.plc_client.write_memories([2,2], False, show_status=False if plc_manager.plc.plc_client.is_connected() else False) #Escribir en M19 (marca que se muestra en la pantalla del LOGO, que está conectado al servidor)


async def plc_reconnection():
    while True:
        plc_manager.plc.plc_client.plc_reconnection()
        await asyncio.sleep(4)


async def plc_watchdog(plc: PLCControl) -> None:
    """
    Lee el estado de las marcas de memoria cada 2 segundos. Cuando es comparado el 
    estado actual de la memoria con el último estado de la memoria, puedo saber qué
    modo fue activado.

    ¿Por qué marcas de memorias y no salidas físicas? Porque las salidas físicas pueden
    ser activadas de cualquier manera (remoto, manual local o automáticamente en local)
    pero cada modo y salida tiene una marca que directamente activa su electroválvula
    correspondiente.
    """

    while True:
            memories_status = plc.read_memories() 
            if memories_status is None:
                await sleep(5) #Espero un poco más por si hay algún problema de comunicación que no trate de leer las memorias contantemente.
                continue
            for name, address in plc.direcciones_act_local_plc.items():
                if address not in plc.active_memories:
                    if memories_status[address[0]][address[1]]:
                        plc.active_memories.append(address)
                        message = f"Activado desde el PLC: {name} "
                        write_history("logo", message)

                if address in plc.active_memories:
                    if not memories_status[address[0]][address[1]]:
                        del plc.active_memories[plc.active_memories.index(address)]
            await sleep(2) #Cada 2 segundos leo el estado de las memorias
