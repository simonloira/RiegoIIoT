import asyncio
from json import dumps
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from backend.history.history_manager import HistorySave, get_history_saver
from backend.PLC.models import BasesTime
from backend.PLC.plc_manager import PLCControl, get_plc
from server.models import PLCDataResponse, SocketMessageResponse, SocketRequest

router = APIRouter()
# Esto se usa para hacer broadcast del diccionario time_data y que llegue en
# tiempo real a todos los clientes
connected_clients: set[WebSocket] = set()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    plc: Annotated[PLCControl, Depends(get_plc)],
    history: Annotated[HistorySave, Depends(get_history_saver)],
) -> None:

    await websocket.accept()
    assert websocket.client, "Websocket.client es None"
    history.save_client_status(websocket.client.host, "connected")
    connected_clients.add(websocket)
    try:
        await websocket.send_text(dumps({"timeZonesSecs": plc.TIME_DATA}))
        data_send: dict

        while True:
            estadosSistema_salidas_dirSalidas = [
                plc.obtener_estados(),
                plc.outputs_addresses,  # Cambia la apariencia de los botones de las zonas | Salida activada: color verde. Desactivada: color gris.
            ]  # Estados del PLC

            data_send = {
                "logoConectado": plc.plc_client.is_connected(),
                "entradas-salidas-dirSalidas": estadosSistema_salidas_dirSalidas,
                "last-activation": history.history["last-activation"],
            }

            # print(f"\nSending: {data_send}\n")
            await websocket.send_text(dumps(data_send))

            # Esperar mensaje del cliente
            try:
                msg = await asyncio.wait_for(
                    websocket.receive_text(), timeout=0.5
                )
                print(msg)
                response = handle_client_messages(msg, plc, history)
                print("Response_client: ", response)
                if response.broadcast:
                    print("Se envía timeZonesSecs")
                    # Envía el diccionario con los tiempos a todos los clientes
                    await broadcast(response.model_dump())
                else:
                    print(f"\nNo tendría que enviar timeZonesSecs: {response}")
                    await websocket.send_json(response.model_dump())

            except asyncio.TimeoutError:
                pass

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        print("Cliente desconectado")
        history.save_client_status(websocket.client.host, "disconnected")


def build_plc_data_resp(
        plc: PLCControl, history:HistorySave
    ) -> PLCDataResponse:

async def broadcast(data: dict[str, int]) -> None:
    client: WebSocket
    disconnected: list[WebSocket] = []
    for client in connected_clients:
        print("Se envía timeZonesSecs a todos")
        try:
            await client.send_text(dumps(data))
        except Exception:
            disconnected.append(client)

    # Eliminar los que se desconectaron
    for client in disconnected:
        connected_clients.remove(client)


def handle_zone_act(
    request: SocketRequest, plc: PLCControl, history: HistorySave
) -> SocketMessageResponse:
    # Botón de activación de x zona en index.html
    result = plc.zone_activation(
        zone=request.zone, activation_time=request.act_time
    )
    if result is None:
        return SocketMessageResponse(
            status="error",
            event=request.command,
            error_msg="Error leyendo buffer de memoria o sistema inestable.",
            broadcast=False,
        )
    history.save_output_status(result)
    return SocketMessageResponse(
        status="success",
        event=request.command,
        data=result.model_dump(),
        broadcast=False,
    )


def handle_time_zone(
    request: SocketRequest, plc: PLCControl, history: HistorySave
) -> SocketMessageResponse:
    time_data = (request.act_time, BasesTime.MINUTES.value)
    plc.save_time(f"T.Remote-{request.zone}", time_data)

    return SocketMessageResponse(
        status="success",
        event=request.command,
        data={"timeZonesSecs": plc.TIME_DATA},
        broadcast=True,
    )


MSG_ACTIONS_MAP = {
    "activate-zone": handle_zone_act,
    "change-zone-time": handle_time_zone,
}


def handle_client_messages(
    client_json: str, plc: PLCControl, history: HistorySave
) -> SocketMessageResponse:
    try:
        print(client_json)
        # Mensajes recibidos desde el cliente
        request = SocketRequest.model_validate_json(client_json)

        print("Client_data: ", request)
        print(f"Client_data.Comando: {request.command}")

        func = MSG_ACTIONS_MAP.get(request.command)
        if func is None:
            return SocketMessageResponse(
                status="error",
                event=request.command,
                error_msg="No existe el comando",
                broadcast=False,
            )
        response = func(request=request, plc=plc, history=history)
        return response

    except ValidationError as e:
        print(e)
        return SocketMessageResponse(
            status="error",
            event="unknown",
            error_msg="Error validando el JSON",
            broadcast=False,
        )
