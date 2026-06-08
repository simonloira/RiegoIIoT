import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.clima import weather_manager
from backend.clima.weather_data_extractor import WeatherMain
from backend.crud.utils import create_meteogal_table
from backend.history import history_manager
from backend.history.activation_history import HistorySaver
from backend.PLC import plc_manager
from backend.PLC.plc_controller import PLCController
from server.routes_pages import router as pages_router
from server.routes_ws import router as ws_router
from server.tasks import (
    automatic_get_weather,
    plc_reconnection,
    plc_watchdog,
    server_heartbeat,
)


class Server:
    def __init__(self) -> None:
        self.app = FastAPI(lifespan=self.lifespan)
        # Static + Routers
        self.app.mount(
            "/static",
            StaticFiles(
                directory=Path(__file__).parent.absolute()
                / "frontend/static"
            ),
            name="static",
        )
        self.app.include_router(pages_router)
        self.app.include_router(ws_router)

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> Any:
        print("Servidor arrancando...")
        create_meteogal_table()
        history_manager.history_handler = HistorySaver()
        plc_manager.plc = PLCController(
            save_history=history_manager.history_handler.save_output_status
        )
        weather_manager.get_weather = WeatherMain()

        plc_manager.plc.stop_plc()  # Detengo todo por si quedó alguna salida activada, que no debería pero bueno

        asyncio.create_task(
            plc_watchdog(plc_manager.plc, history_manager.history_handler)
        )  # Comprueba la activación de las salidas desde el PLC
        asyncio.create_task(
            automatic_get_weather(plc_manager.plc, weather_manager.get_weather)
        )  # [[aemet_7d, aemet_h], [meteogal]]
        asyncio.create_task(
            server_heartbeat(plc_manager.plc)
        )  # Envío al PLC el estado de conexión al servidor
        asyncio.create_task(
            plc_reconnection(plc_manager.plc)
        )  # Tarea de comprobación si está el PLC conectado, y si no, reconectar

        yield  # NOTA: Todo lo que está antes es startup, después del yield es shutdown

        print("Servidor cerrando: apagando PLC...")
        plc_manager.plc.stop_plc()
        input("Pulsa enter: ")


if __name__ == "__main__":
    import uvicorn

    # setup_logging()
    uvicorn.run(Server().app, host="0.0.0.0", port=8000, reload=False)
