import asyncio
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from backend.history import history_manager
from backend.history.activation_history import HistorySaver
from server.routes_pages import router as pages_router
from server.routes_ws import router as ws_router
from server.tasks import automatic_get_weather, server_heartbeat, plc_reconnection

from backend.PLC.plc_controller import PLCController
from backend.clima.extraer_datos_clima import WeatherMain
from backend.history.activation_history import setup_logging
#Class managers
from backend.PLC import plc_manager
from backend.clima import weather_manager

class Server:
    def __init__(self)-> None:
        self.app = FastAPI(lifespan=self.lifespan)
        # Static + Routers
        self.app.mount(
            "/static",
            StaticFiles(
                directory=Path(__file__).parent.parent.absolute()
                / "riegoAutomatico/frontend/static"
            ),
            name="static",
        )
        self.app.include_router(pages_router)
        self.app.include_router(ws_router)

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> Any:
        print("Servidor arrancando...")
        plc_manager.plc = PLCController()
        weather_manager.get_weather = WeatherMain()
        history_manager.history_handler = HistorySaver()

        plc_manager.plc.stop_plc() #Detengo todo por si quedó alguna salida activada, que no debería pero bueno

        asyncio.create_task(plc_manager.plc.plc_watchdog()) #Comprueba la activación de las salidas desde el PLC
        asyncio.create_task(automatic_get_weather()) #[[aemet_7d, aemet_h], [meteogal]]
        asyncio.create_task(server_heartbeat()) #Envío al PLC el estado de conexión al servidor
        asyncio.create_task(plc_reconnection()) #Tarea de comprobación si está el PLC conectado, y si no, reconectar

        yield  # NOTA: Todo lo que está antes es startup, después del yield es shutdown

        print("Servidor cerrando: apagando PLC...")
        plc_manager.plc.stop_plc()
        input("Pulsa enter: ")



if __name__ == "__main__":
    import uvicorn
    # setup_logging()
    uvicorn.run(Server().app, host="0.0.0.0", port=8000, reload=False)

