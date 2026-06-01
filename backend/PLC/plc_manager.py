# Declaración del objeto plc. Se crea el objeto en main.py
from backend.PLC.plc_controller import PLCController

type PLCControl = PLCController

plc: PLCController | None = None

def get_plc() -> PLCController:
    #Se comprueba si plc es
    assert plc is not None, "El PLC no se inicializó"
    return plc
