import backend.PLC.rwConnectLogo as rwConnectLogo
from backend.history.activation_history import write_history, write_last_activation
from backend.history.time_server import seconds_to_hour
from asyncio import sleep, create_task, CancelledError
from backend.basics.json_tools import load_json_file, save_json_file
from backend.PLC.models import (
    ActivationTask,
    Buffer,
    LocalMemoriesStatus,
    PLCAddress,
    TagName,
    VirtualMemories,
    ZoneActivationInfo,
    ZonesMemories,
    PLCTimer,
    BasesTime
)
from settings import settings


class PLCController:
    def __init__(self) -> None:
        self.memorie_bytes_read = settings.MEMORIE_BYTES_READ
    #Carga las direcciones del PLC
        # BYTES_VM: TManuales zona y TAutomáticos zona: [wordTiempo(byte, byte+1), byteBaseTiempo(s/m/h)] 
        # | weekly_timer[bytedías_acivados, wordontime, wordofftime] | astro-clock[wordSunriseOffsetTime]
        self.BYTES_VM = VirtualMemories(**load_json_file(settings.VM_PATH)) #Importa las memorias virtuales (contadores de zonas, días de activación...)
        # TIME_DATA: {"zona": t_activación (int)}
        self.TIME_DATA:dict[TagName,int] = load_json_file(settings.TZ_PATH) #Tiempo de riego de las zonas en segundos
        # ADDRESS_SSM: {"zona": [byteIndex, bitIndex]}
        self.BYTES_SSM:dict[str,PLCAddress] = load_json_file(settings.SSM_PATH) #Direcciones de memoria de los estados del sistema (StatusSystemMemories)
      #Direcciones de memoria de las zonas de riego
        BYTES_ZM = ZonesMemories(**load_json_file(settings.ZM_PATH))
        ##Los siguientes datos siguen la estructura: #"zona":[Byte index, bool index]
        self.remote_addresses = BYTES_ZM.web_control
        self.local_act_addresses = BYTES_ZM.local_act #Control automático programado en PLC y control manual desde el PLC
        self.outputs_addresses = BYTES_ZM.outputs

        self.plc_client = rwConnectLogo.ReadWritePLC()
        self.buffer_memories: None | Buffer #Se lee en la función plc_watchdog cada dos segundos y se usa con la función read_memorie
        self.active_memories:list[PLCAddress] = []
        self.active_tasks:dict[str, ActivationTask] = {}

    def get_status_memories(self) -> dict[str, bool|None] | None:
        if self.buffer_memories is None:
            return None

        status_memories:dict[str, bool|None] = {}
        for memorie_name, memorie_address in self.BYTES_SSM.items():
            status_memories[memorie_name] = self.plc_client.read_memory(
                memorie_address,
                self.buffer_memories
            )
        return status_memories

    def obtener_estados(self) -> tuple[dict[str, bool|None] | None,
                                                 list[bool] | None]:
        # self.entradas = self.plc_client.leer_entradas() Esto no se debe
        # mandar, esto se usa para mostrar el nivel del pozo en el frontend.
        # Pero lo que tengo que hacer es en el LogoSoft crear unos estados de
        # nivel del pozo y mandarlos al frontend y desde ahí que se muestre el
        # nivel.
        outputs = self.plc_client.leer_salidas()
        status_memories = self.get_status_memories()
        return status_memories, outputs

    def __cancel_task(self, name_task:str) -> None:
        # Cancelar task si existe
        if name_task in self.active_tasks:
    # def check_well_level(self):
    #     if (self.entradas is None) or (self.entradas == []):
    #         return
    #     if not self.entradas[1]: #Si no se detecta señal del interruptor boya, se apagan todas las salidas del PLC
    #         print("\nNivel del pozo bajo, se detienen todas las salidas")
    #         self.stop_plc(off_only_zones=True)

    def stop_plc(self, off_only_zones:bool=False) -> None:
        """Stops all PLC outputs"""
        print("Deteniendo todo")

        memories_status = self.plc_client.read_buffer_memories()
        if memories_status is None:
            print("Error leyendo memorias = None")
            return

        for zona, direccion in self.remote_addresses.items():
            if self.plc_client.read_memory(direccion, memories_status):
                self.__cancel_task(name_task=zona)
                self.plc_client.write_memory(self.remote_addresses[zona],
                                              False)

        print("Estado salidas: ", self.plc_client.read_outputs())

        if not off_only_zones:
            #Desactivar M18 y M19 (lloverá, servidor conectado respectivamente)
            self.plc_client.write_memory(self.BYTES_SSM["Lluvia"], False)
            self.plc_client.write_memory((2,2), False)
    
    def write_raining_memorie(self, rain): #Se llama en tasks.py después de obtener la información climatológica
        #Memoria: M18(M2.1)
        self.plc_client.write_memories(self.BYTES_SSM["Lluvia"], rain)
    
    def save_time(self, value:list, memory_name:str):
        self.plc_client.write_VM(value, self.BYTES_VM[memory_name])
        zone = memory_name.split("-")[1]
        self.TIME_DATA[zone] = value[0]
        save_json_file("timeData", PLCSettings.TZ_PATH, self.TIME_DATA)

    async def plc_watchdog(self):
        while True:
            memories_status = self.plc_client.read_memories() 
            if memories_status is None:
                await sleep(5) #Espero un poco más por si hay algún problema de comunicación que no trate de leer las memorias contantemente.
                continue
            for name, address in self.direcciones_act_local_plc.items():
                if address not in self.active_memories:
                    if memories_status[address[0]][address[1]]:
                        self.active_memories.append(address)
                        message = f"Activado desde el PLC: {name} "
                        write_history("logo", message)
                
                if address in self.active_memories:
                    if not memories_status[address[0]][address[1]]:
                        del self.active_memories[self.active_memories.index(address)]
            await sleep(2) #Cada 2 segundos leo el estado de las memorias
    
    async def shutdown_output_PLC(self, zone:str, activation_time:int):
        try:
            await sleep(activation_time)
            self.plc_client.write_memories(self.direcciones_remoto_zonas[zone], False)
            write_message_history(f"La zona {zone} terminó de regarse", activation_time)
            write_last_activation(f"La zona {zone} fue regada durante:", seconds_to_hour(activation_time)) #seconds_to_hour -> (hour, minutes, seconds)
        except CancelledError:
            print(f"Apagado automático de {zone} cancelado por forzado apagado")
        finally:
            self.active_tasks.pop(zone, None) #Da igual si da error o no que al terminar de ejecutarse el bloque se elimina la tarea
