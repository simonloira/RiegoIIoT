import asyncio
from json import loads, dumps
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.login import login
from backend.history.activation_history import history, write_history
import backend.clima.weather_manager as weather_manager
from backend.login.secure_token import check
from backend.PLC import plc_manager

router = APIRouter()
check_token = check()
connected_clients = set() #Esto se usa para hacer broadcast del diccionario time_data y que llegue en tiempo real a todos los clientes

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    send_history = write_history("add_ip", f"{websocket.client[0]}")
    connected_clients.add(websocket)
    try:
        await websocket.send_text(dumps({"timeZonesSecs": plc_manager.plc.TIME_DATA}))
        data_send: dict

        while True:

            entradas_salidas_dirSalidas = [
                plc_manager.plc.obtener_estados(),
                plc_manager.plc.direcciones_salida, #Cambia la apariencia de los botones de las zonas | Salida activada: color verde. Desactivada: color gris.
            ]  # Estados del PLC

            data_send = {
                "logoConectado": plc_manager.plc.plc_client.is_connected(),
                "entradas-salidas-dirSalidas": entradas_salidas_dirSalidas,
                "last-activation": history["last-activation"],
            }

            if send_history:
                print(f"Enviando history: {history}")
                send_history = False
                data_send.update({"history": history})

            # print(f"\nSending: {data_send}\n")
            await websocket.send_text(dumps(data_send))

            # Esperar mensaje del cliente
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                data_send, info_time_zone = handle_client_messages(
                    message
                )
                send_time_data = info_time_zone[0] #info_time_zone = [send_time, zones_time_data]
                if send_time_data:
                    time_data = info_time_zone[1] 
                    await broadcast({"timeZonesSecs": time_data}) #Envía el diccionario con los tiempos a todos los clientes
                else:
                    print(f"\nTendría que enviar history: {data_send}")
                    await websocket.send_text(dumps(data_send))

            except asyncio.TimeoutError:
                pass

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        print("Cliente desconectado")
        send_history = write_history("remove_ip", f"{websocket.client[0]}")


async def broadcast(data:dict):
    client:WebSocket
    disconnected = []
    for client in connected_clients:
        try:
            await client.send_text(dumps(data))
        except Exception:
            disconnected.append(client)

    # Eliminar los que se desconectaron
    for client in disconnected:
        connected_clients.remove(client)


def handle_client_messages(client_message):
    client_data = loads(client_message) #Mensajes recibidos desde el cliente
    cmd = client_data.get("comando", "") #Se coge la key "comando" en json recibido desde el cliente
    send_time = False #Permite enviar al cliente el tiempo de riego configurado
    print(f"Comando {cmd}")
    zones_time_data = plc_manager.plc.TIME_DATA

    if "act" in cmd: #Botón de activación de x zona en index.html
        plc_manager.plc.ejecutar_comando(cmd, client_data.get("t_activacion", ""))
        data_send = {"history": history}

    elif cmd == "refresh_history": #Botón de refresco en history.html
        data_send = {"history": history}

    elif cmd == "refresh_weather": #Al actualizar la la página en index.html
        print("Consiguiendo datos clima...")
        weather_data = weather_manager.get_weather.read_last_saved_data(apis=["aemet", "meteogalicia"]) #weather_data = [True, [[aemet_7d, aemet_h], [meteogal]]] 
        data_send = {"weatherData": weather_data}  #Envío [[aemet_7d, aemet_h], [meteogal]]

    elif "change_zone_time" in cmd:
        activation_time = int(client_data.get("t_activacion", ""))
        zone = cmd.split("-")[1]

        plc_manager.plc.save_time([activation_time, 2], f"T.Remote-{zone}")
        zones_time_data = plc_manager.plc.TIME_DATA

        data_send = {"timeZonesSecs": zones_time_data}
        send_time = True
    return data_send, [send_time, zones_time_data]



