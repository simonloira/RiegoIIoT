# Lo importo en rwConnectLogo y en plc_controller
import logging
from dataclasses import dataclass
from os import environ
from pathlib import Path
from typing import Final, Literal

from load_var_env import load_vars_env

# --- Configuración de la Aplicación ---
MAIN_PATH: Final[Path] = Path(__file__).resolve().parent
load_vars_env()


@dataclass
class Settings:
    STATE_LEVEL: Final[Literal[20]] = logging.INFO
    # 1. Configuración de rutas
    # Login
    USER: Final[str] = environ["USER_LOGIN"]
    PASSWORD: Final[str] = environ["PASSWORD_LOGIN"]
    SECRET_KEY: Final[str] = environ["SECRET_JWT_KEY"]
    ACCESS_TOKEN_MINUTES: Final[int] = 120
    # Clima
    MAIN_CLIMATE_PATH: Final[Path] = Path(MAIN_PATH / "backend" / "clima")
    CLIMATE_DATA_PATH: Final[Path] = Path(MAIN_CLIMATE_PATH / "datos_clima")
    CONFIG_APIS_FILE_PATH: Final[str] = str(
        MAIN_CLIMATE_PATH / "datos_clima" / "CLIMATE_APIS_CONFIG.json"
    )
    METEOGAL_API: Final[str] = environ["METEOGALICIA_API_KEY"]
    # PLC
    VM_PATH: Final[str] = str(
        MAIN_PATH / "backend" / "PLC" / "config" / "virtualMemories.json"
    )
    ZM_PATH: Final[str] = str(
        MAIN_PATH / "backend" / "PLC" / "config" / "zonesMemories.json"
    )
    TZ_PATH: Final[str] = str(
        MAIN_PATH / "backend" / "PLC" / "config" / "timeZonesData.json"
    )
    SSM_PATH: Final[str] = str(
        MAIN_PATH / "backend" / "PLC" / "config" / "statusSystemMemories.json"
    )

    # 2. Configuración del PLC
    MEMORIE_BYTES_READ: Final[int] = 5  # Bytes de memoria a leer
    IP_LOGO: Final[str] = "192.168.2.252"  # "192.168.2.252"
    LOCAL_TSAP: Final[Literal[8192]] = 0x2000
    REMOTE_TSAP: Final[Literal[4096]] = 0x1000

    # 3. Configuración del Servidor
    SERVER_HOST: Final[str] = "0.0.0.0"
    SERVER_PORT: Final[int] = 8000
    DEBUGGING: Final[bool] = False


# 4. Constantes de Tarea ya veré en algún momento si me interesa poner
# un archivo de configuración de marcas.
# HEARTBEAT_ADDRESS: tuple = (2, 2) # M19

# Creamos una única instancia de la clase Settings
settings = Settings()
