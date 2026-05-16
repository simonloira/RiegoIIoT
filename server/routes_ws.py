import asyncio
from json import dumps, loads
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.login import login
from backend.history.activation_history import history, write_history
import backend.clima.weather_manager as weather_manager
import backend.history.history_manager as history_manager
from backend.login.secure_token import check
from backend.PLC import plc_manager

router = APIRouter()
check_token = check()
history = history_manager.history_handler
connected_clients:set[WebSocket] = set()  # Esto se usa para hacer broadcast del diccionario time_data y que llegue en tiempo real a todos los clientes

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    history.save_client_status("Se ha conectado: ", websocket.client.host)
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
                "last-activation": history_manager.history_handler.history["last-activation"],
            }

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
                    print("Se envía timeZonesSecs")
                    # Envía el diccionario con los tiempos a todos los clientes
                    await broadcast(client_resp)
                else:
                    print(f"\nNo tendría que enviar timeZonesSecs: {client_resp}")
                    await websocket.send_text(dumps(client_resp))

            except asyncio.TimeoutError:
                pass

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        print("Cliente desconectado")
        history_manager.history_handler.save_client_status(
            "Se ha desconectado: ", websocket.client.host
        )


async def broadcast(data: dict) -> None:
    client: WebSocket
    disconnected:list[WebSocket] = []
    for client in connected_clients:
        print("Se envía timeZonesSecs a todos")
        try:
            await client.send_text(dumps(data))
        except Exception:
            disconnected.append(client)

    # Eliminar los que se desconectaron
    for client in disconnected:
        connected_clients.remove(client)


    if "act" in cmd:  # Botón de activación de x zona en index.html
        #Refactorizando la activación
        pass

    elif cmd == "refresh_weather":  # Al actualizar la la página en index.html
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



