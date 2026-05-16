from datetime import datetime
from typing import Final

type category_history = dict[str, str | tuple[str, tuple[int, ...]]]

class HistorySaver:
    def __init__(self) -> None:
        # Ejemplo:
        # {'server': {'{ip_cliente}': 'Conectado {nombre_cliente}'},
        # "logo":{'{datetime}': }
        # }'
        # TODO: Reemplazar almacenamiento en RAM por almacenamiento persistente
        # con SQLite3
        self.history: dict[str, category_history]
        self.history = {"server": {}, "logo": {}, "last-activation":{}}
        self.IPS_IDS: Final[dict[str, str]] = {} #IPs dispositivos conocidos

    def save_output_status(self, msg:str, activation_time:int) -> None:
        """Método único para evitar código duplicado"""
        self._save_last_activation(msg, activation_time)
        self._save_PLC_status(msg, activation_time)
        print("History: ", self.history)

    def save_client_status(self, message: str, ip: str)-> None:
        client_name = self.__get_id_ip(ip)
        self.history["server"][self._encode_ip(ip)] = message + client_name

    def _save_last_activation(self, message: str, secs_act: int) -> None:
        timestamp, real_t_act = self._build_value(secs_act)
        last_activation = (message, real_t_act)
        self.history["last-activation"][str(timestamp)] = last_activation

    def _save_PLC_status(self, message: str, secs_act: int) -> None:
        timestamp, real_t_act = self._build_value(secs_act)
        h, m, s = real_t_act

        message += f" {h:02d}h {m:02d}m {s:02d}s"
        self.history["logo"][str(timestamp)] = message

    def _build_value(self, secs_act: int) -> tuple[datetime, tuple[int, ...]]:
        date = datetime.now()
        h, m, s = self._seconds_to_hour(secs_act)
        return date, (h, m, s)

    def _seconds_to_hour(self, total_seconds:int) -> tuple[int, int, int]:
        hour = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        return hour, minutes, seconds

    def _encode_ip(self, ip_client: str) -> str:
        ip_parts = ip_client.split(".")
        ip_parts[1] = "x" * len(ip_parts[1])
        ip_parts[2] = "x" * len(ip_parts[2])
        ip_parts[3] = "x" * len(ip_parts[3])

        return f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{ip_parts[3]}"

    def __get_id_ip(self, ip:str) -> str:
        if ip in self.IPS_IDS.keys():
            return f"{self.IPS_IDS[ip]}"
        return "DISPOSITIVO DESCONOCIDO"

        # history[element][key] = [timestamp, message] #Para los dispositivos
        # conectados y desconectados. La key sería la IP
