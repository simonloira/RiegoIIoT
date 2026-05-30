from asyncio import CancelledError, create_task, sleep
from typing import Callable

import backend.PLC.rwConnectLogo as rwConnectLogo
from backend.basics.json_tools import load_json_file, save_json_file
from backend.history.models import ZoneActivation
from backend.PLC.models import (
    ActivationTask,
    BasesTime,
    Buffer,
    LocalMemoriesStatus,
    PLCAddress,
    PLCTimer,
    TagName,
    VirtualMemories,
    ZonesMemories,
)
from settings import settings


class PLCController:
    def __init__(self, save_history: Callable[[ZoneActivation], None]) -> None:
        self.memorie_bytes_read = settings.MEMORIE_BYTES_READ
      # Carga las direcciones del PLC
        self.BYTES_VM = VirtualMemories(
            **load_json_file(settings.VM_PATH)
        )  # Importa las memorias virtuales (contadores de zonas, días de
           # activación...)
        # TIME_DATA: {"zona": t_activación (int)}
        self.TIME_DATA: dict[TagName, int] = load_json_file(
            settings.TZ_PATH
        )  # Tiempo de riego de las zonas en segundos
        # ADDRESS_SSM: {"zona": [byteIndex, bitIndex]}
        self.BYTES_SSM: dict[str, PLCAddress] = load_json_file(
            settings.SSM_PATH
        )  # Direcciones de memoria de los estados del sistema
           # (StatusSystemMemories)
        # Direcciones de memoria de las zonas de riego
        BYTES_ZM = ZonesMemories(**load_json_file(settings.ZM_PATH))
        self.remote_addresses = BYTES_ZM.web_control
        self.local_act_addresses = (
            BYTES_ZM.local_act
        )  # Control automático programado en PLC y control manual desde el PLC
        self.outputs_addresses = BYTES_ZM.outputs
        self.save_history = save_history
        self.plc_client = rwConnectLogo.ReadWritePLC()
        self.buffer_memories: (
            None | Buffer
        )  # Se lee en la función plc_watchdog cada dos segundos y se usa con
           # la función read_memory
        self.active_memories: list[PLCAddress] = []
        self.active_tasks: dict[str, ActivationTask] = {}

    def get_status_memories(self) -> dict[str, bool | None] | None:
        if self.buffer_memories is None:
            return None

        status_memories: dict[str, bool | None] = {}
        for memorie_name, memorie_address in self.BYTES_SSM.items():
            status_memories[memorie_name] = self.plc_client.read_memory(
                memorie_address, self.buffer_memories
            )
        return status_memories

    def zone_activation(
        self, zone: str, activation_time: int
    ) -> ZoneActivation | None:
        if self.buffer_memories is None:
            return None

        if not self.plc_client.read_memory(
            self.BYTES_SSM["SistemaEstable"], self.buffer_memories
        ):
            return None
    def __cancel_task(self, name_task: str) -> None:
        # Cancelar task si existe
        if name_task in self.active_tasks:
            self.active_tasks[name_task].task.cancel()

    # def check_well_level(self):
    #     if (self.entradas is None) or (self.entradas == []):
    #         return
    #     if not self.entradas[1]: #Si no se detecta señal del interruptor
    #                              #boya, se apagan todas las salidas del PLC
    #         print("\nNivel del pozo bajo, se detienen todas las salidas")
    #         self.stop_plc(off_only_zones=True)

    def stop_plc(self, off_only_zones: bool = False) -> None:
        """Stops all PLC outputs"""
        print("Deteniendo todo")

        memories_status = self.plc_client.read_buffer_memories()
        if memories_status is None:
            print("Error leyendo memorias = None")
            return

        for zona, direccion in self.remote_addresses.items():
            if self.plc_client.read_memory(direccion, memories_status):
                self.__cancel_task(name_task=zona)
                self.plc_client.write_memory(
                    self.remote_addresses[zona], False
                )

        print("Estado salidas: ", self.plc_client.read_outputs())

        if not off_only_zones:
            # Desactivar M18 (lloverá) y M19 (Servidor conectado)
            self.plc_client.write_memory(self.BYTES_SSM["Lluvia"], False)
            self.plc_client.write_memory((2, 2), False)

    def write_raining_memorie(self, rain: bool) -> None:
         # Se llama en tasks.py después de obtener la información climatológica
        # Memoria: M18(M2.1)
        self.plc_client.write_memory(self.BYTES_SSM["Lluvia"], rain)

    def turn_off_zone(self, zone: str) -> None:
        """Encapsula la escritura física"""
        address = self.remote_addresses[zone]
        return self.plc_client.write_memory(address, False)

    def save_time(
        self, memory_name: TagName, values_w: tuple[int, int]
    ) -> None:
        """ Para escribir el tiempo directamente en el LOGO! simplemente es
        coger la dirección del DB donde está almacenado el dato de edición de
        tiempo de cada zona y se convierte el valor en segundos a hexadecimal,
        se escribe el valor y listo.

        Args:
            memory_name (TagName): Nombre del tipo de temporizador asignado a
             la zona.
            values_w (tuple[int, int]): Tiempo en segundos y base de tiempo.
        """
        timer = self.BYTES_VM.root[memory_name]
        assert isinstance(timer, PLCTimer)

        self.plc_client.write_VM(
            self.check_overflow(values_w), (timer.time, timer.timebase)
        )
        zone = memory_name.split("-")[1]
        self.TIME_DATA[zone] = values_w[0]
        save_json_file("timeData", settings.TZ_PATH, self.TIME_DATA)

    def check_overflow(self, values: tuple[int, int]) -> tuple[int, int]:
        # 99 minutos + 59 segundos es el límite que tiene el PLC para la
        # base minutos
        if values[0] > (99 * 60 + 59):
            return (
                int(values[0] / 60),
                BasesTime.HOUR.value,
            )  # Se escribe el tiempo en horas

        return values[0], values[1]

    async def shutdown_output_PLC(
        self, zone: str, activation_time: int
    ) -> None:
        """Apaga la salida del PLC y guarda en el historial el momento en el
        que se desactivó.

        Aunque el apagado de la salida lo gestiona el PLC, esta función
        permite saber cuándo se terminó de regar la zona activada remotamente.

        Args:
            zone (str): Nombre de la zona que se apaga
            activation_time (int): Tiempo en segundos que estuvo activada
        """
        try:
            await sleep(activation_time)
            self.plc_client.write_memories(self.direcciones_remoto_zonas[zone], False)
            write_message_history(f"La zona {zone} terminó de regarse", activation_time)
            write_last_activation(f"La zona {zone} fue regada durante:", seconds_to_hour(activation_time)) #seconds_to_hour -> (hour, minutes, seconds)
        except CancelledError:
            print(f"Apagado automático cancelado forzado apagado de {zone}")
        finally:
            # Da igual si da error cualquier otro error o no que al terminar de
            # ejecutarse el bloque se elimina la tarea
            self.active_tasks.pop(zone, None)
