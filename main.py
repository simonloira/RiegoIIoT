import asyncio
import logging
import sys
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
from settings import settings


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
        root.info("Iniciando tareas del servidor...")
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
        ) # Tarea de comprobación si está el PLC conectado, y si no, reconectar

        yield  # NOTA: Lo que está antes es startup, después es shutdown

        root.info("Apagando salidas del PLC...")
        plc_manager.plc.stop_plc()


class AnsiColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        no_style = '\033[0m'
        green = '\033[32m'
        bold = '\033[91m'
        yellow = '\033[93m'
        red = '\033[31m'
        red_light = '\033[91m'
        start_style = {
            'DEBUG': no_style,
            'INFO': green,
            'WARNING': yellow,
            'ERROR': red,
            'CRITICAL': red_light + bold,
        }.get(record.levelname, no_style)
        end_style = no_style
        return f'{start_style}{super().format(record)}{end_style}'

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(
        filename='riegoiiot.log',
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%m/%d/%Y %H:%M:%S %z'
    )
    root = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)

    root.setLevel(settings.STATE_LEVEL)
    handler.setLevel(settings.STATE_LEVEL)

    f = '{asctime} | {levelname:<8s} | {name:<20s} | {message}'
    formatter = AnsiColorFormatter(f, style='{')
    handler.setFormatter(formatter)

    root.addHandler(handler)

    uvicorn.run(
        Server().app,
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=False
    )
