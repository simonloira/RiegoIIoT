import logging
from time import time, sleep
from backend.history.time_server import get_date

history = {"server":{}, "logo":{}, "last-activation":()} #Ejemplo: {'server': {('19 de Sept. de 2025', '01:10:08'): 'Iniciando servidor...}, "logo:{}"}'
ips_connected = []
new_date = get_date()

#AppData/Local/Programs/Python/Python313/Lib/logging/__init__.py/Logger/info
def write_last_activation(message:str, real_t_act:tuple):
    global history
    timestamp = new_date.get_current_date(time())
    history["last-activation"] = (timestamp, message, real_t_act)

def add_status(element:str, message:str, key=None):
    global history #No es necesario meter esto ya que no da error sin esto pero, es más legible así
    timestamp = new_date.get_current_date(time())
    if key != None:
        history[element][key] = [timestamp, message] #Para los dispositivos conectados y desconectados. La key sería la IP
        return
    history[element][timestamp] = message
    sleep(1)

def get_id_ip(ip):
    if ip in IPS_IDS.keys():
        return f"{IPS_IDS[ip]}"
    return "DISPOSITIVO DESCONOCIDO"

def encode_ip(ip_client:str):
    ip_show = ip_client.split(".")
    ip_show[1] = "x" * len(ip_show[1])
    ip_show[2] = "x" * len(ip_show[2])
    ip_show[2] = "x" * len(ip_show[3])
    ip_show = f"{ip_show[0]}.{ip_show[1]}.{ip_show[2]}.{ip_show[3]}"
    return ip_show

def remove_ip(ip_client:str):
    if ip_client in ips_connected:
        del ips_connected[ips_connected.index(ip_client)]
        ip_show = encode_ip(ip_client=ip_client)
        add_status("server", 
                   f"{get_id_ip(ip_client)} desconectado",
                   ip_show)

def add_ip(ip_client:str):
    if ip_client not in ips_connected:
        ips_connected.append(ip_client)
        ip_show = encode_ip(ip_client=ip_client)
        add_status("server", 
                   f"{get_id_ip(ip_client)} conectado", 
                   ip_show)

def check_message_server(server_logger:str):
    AUTH_MESSAGES = {"INFO: Application startup complete.": "Iniciando servidor...",
                     'INFO: Uvicorn running on': "¡Servidor iniciado correctamente!",
                    }
    for auth_message in AUTH_MESSAGES.keys():
        if (auth_message == server_logger) or (auth_message in server_logger):
            add_status("server", AUTH_MESSAGES[auth_message])
    
    
def write_history(command:str, param:str): #Punto de llamada desde cualquier otro archivo
    """Escribe información para el historial del servidor.
        Commands:
        'add_ip': Guarda la IP del cliente que se conecta y la formatea para guardarla en el historial (param=IP_cliente)
        'remove_ip': Borra la IP del cliente que se desconecta y muestra un mensaje de dispositivo desconectado (param=IP_cliente)
        'logo': Añade un estado de activación del LOGO (param=menesja personalizado)"""
    
    if command == "add_status": #Sólo se usa este comando cuando la función es llamada por el logger
        print("add_status ", param)
        check_message_server(param)
    elif command == "add_ip":
        print("Add_ip")
        add_ip(param)
    elif command == "remove_ip":
        print("remove_ip")
        remove_ip(param)
    elif command == "logo":
        print("logo")
        add_status("logo", param)
    else:
        return False
    return True


class HistoryHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        write_history("add_status", msg)
        

def setup_logging():
    history_handler = HistoryHandler()
    history_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    history_handler.setFormatter(formatter)

    logging.getLogger("uvicorn").addHandler(history_handler)
    # logging.getLogger("uvicorn.error").addHandler(history_handler)
    logging.getLogger("uvicorn.access").addHandler(history_handler)
    logging.getLogger().addHandler(history_handler)

