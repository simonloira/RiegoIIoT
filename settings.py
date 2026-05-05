#Lo importo en rwConnectLogo y en plc_controller
from dataclasses import dataclass
from os import getcwd

# --- Configuración de la Aplicación ---

@dataclass
class Settings:
    MAIN_PATH = getcwd()
  # 1. Configuración de rutas
    # Login
    LOGIN_PATH = f"{MAIN_PATH}/backend/login/login.txt"
    # Clima
    MAIN_CLIMATE_PATH = f"{MAIN_PATH}/backend/clima"
    CLIMATE_DATA_PATH = f"{MAIN_CLIMATE_PATH}/datos_clima"
    CONFIG_APIS_FILE_PATH = f"{MAIN_CLIMATE_PATH}/datos_clima/CLIMATE_APIS_CONFIG.json"
    # PLC
    VM_PATH = f"{MAIN_PATH}/backend/PLC/config/virtualMemories.json"
    ZM_PATH = f"{MAIN_PATH}/backend/PLC/config/zonesMemories.json"
    TZ_PATH = f"{MAIN_PATH}/backend/PLC/config/timeZonesData.json"
    SSM_PATH = F"{MAIN_PATH}/backend/PLC/config/statusSystemMemories.json"

  # 2. Configuración del PLC
    MEMORIE_BYTES_READ = 5 #Bytes de memoria a leer
    IP_LOGO: str = "192.168.2.252"
    LOCAL_TSAP = 0x1000
    REMOTE_TSAP = 0x2000
    
  # 3. Configuración del Servidor
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    
  # 4. Constantes de Tarea ya veré en algún momento si me interesa poner 
    # un archivo de configuración de marcas.
    # HEARTBEAT_ADDRESS: tuple = (2, 2) # M19
    
# Creamos una única instancia de la clase Settings
settings = Settings()