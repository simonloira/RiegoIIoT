from time import time
from typing import Final

from backend.history.models import (
    History,
    UserConnected,
    UserEvents,
    ZoneActivation,
)


class HistorySaver:
    def __init__(self) -> None:
        # Ejemplo:
        # {'server': {'{ip_cliente}': 'Conectado {nombre_cliente}'},
        # "logo":{'{datetime}': }
        # }'
        # TODO: Reemplazar almacenamiento en RAM por almacenamiento persistente
        # con SQLite3
        self.history = History()
        self.IPS_IDS: Final[dict[str, str]] = {} #IPs dispositivos conocidos

    def save_output_status(self, info:ZoneActivation) -> None:
        """Método único para evitar código duplicado"""
        if self.history.plc.get(info.zone) is None:
            self.history.plc[info.zone] = []
        self.history.plc[info.zone].append(info)

        self.history.last_activation = info

    def save_client_status(self, ip: str, event: UserEvents)-> None:
        client_name = self._get_id_ip(ip)
        info = UserConnected(
            event=event,
            timestamp=int(time()),
            ip=ip,
            name=client_name
        )

        self.history.users[ip] = info

    def _encode_ip(self, ip_client: str) -> str:
        """
        Ya no sirve. Al principio sí porque se hacía un tunneling
        con ngrok. Pero ahora para acceder desde cualquier parte
        del mundo se usa tailscale que es una red privada.
        """
        ip_parts = ip_client.split(".")
        ip_parts[1] = "x" * len(ip_parts[1])
        ip_parts[2] = "x" * len(ip_parts[2])
        ip_parts[3] = "x" * len(ip_parts[3])

        return f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{ip_parts[3]}"

    def _get_id_ip(self, ip:str) -> str:
        if ip in self.IPS_IDS.keys():
            return f"{self.IPS_IDS[ip]}"
        return "DISPOSITIVO DESCONOCIDO"

        # history[element][key] = [timestamp, message] #Para los dispositivos
        # conectados y desconectados. La key sería la IP
