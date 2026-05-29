from snap7.client import Client
from snap7.type import Areas, Parameter
from snap7.util import get_bool, set_bool

from backend.PLC.models import Buffer, MemoryBlock, PLCAddress
from settings import settings


class PLCConnection:
    def __init__(self) -> None:
        self.client = Client()
        self.connect_PLC()

    def connect_PLC(self) -> None:
        try:
            print("Conectándose al LOGO...")
            self.client.set_connection_params(settings.IP_LOGO,
                                              settings.LOCAL_TSAP, 
                                              settings.REMOTE_TSAP)
            self.client.set_param(Parameter.RecvTimeout, 4000)
            self.client.set_param(Parameter.SendTimeout, 4000)
            self.client.connect(settings.IP_LOGO, 0, 1)
            print("¡Conectado al LOGO correctamente!")
        except Exception as e:
            print("¡IMPOSIBLE CONECTAR AL LOGO!:", e)

    def is_connected(self) -> bool:
        return self.client.get_connected()

    def plc_reconnection(self) -> None: # Hacer la función asíncrona
            try:
                if not self.is_connected():
                    self.connect_PLC()       
            except Exception as e:
                print(f"Error durante el proceso de reconexión: {e}")

class ReadWritePLC(PLCConnection):
    def __init__(self) -> None:
        super().__init__()

    def __error(self) -> None:
        self.client.disconnect()
        self.plc_reconnection()

    # Funciones de lectura/escritura básicas
    def read_inputs(self) -> None | list[bool]:
        try:
            if not self.is_connected():
                return None

            data = self.client.read_area(Areas.PE, 0, 0, 1)

            return [get_bool(data, 0, i) for i in range(8)]

        except Exception as e:
            print(f"Error leyendo las entradas: {e}")
            self.__error()
            return None

    def read_outputs(self) -> None | list[bool]:
        try:
            if not self.is_connected():
                return None

            data = self.client.read_area(Areas.PA, 0, 0, 1)

            return [get_bool(data, 0, i) for i in range(4)]

        except Exception as e:
            print(f"Error leyendo las salidas: {e}") 
            self.__error()
            return None

    def write_memory(self,
                      memorie_adress:PLCAddress,
                      state_to_write:bool) -> None:

        if not self.is_connected():
            return None

        B_index = memorie_adress[0]
        b_index = memorie_adress[1]
        memory_number = B_index * 8 + b_index + 1

        try:
            data = self.client.read_area(Areas.MK, 0, B_index, 1)
            set_bool(data, 0, b_index, state_to_write)
            self.client.write_area(Areas.MK, 0, B_index, data)

            if settings.DEBUGGING:
                print(f"Escrito '{state_to_write}' en M", memory_number)

        except Exception as e:
            print(f"Error escribiendo memoria M{memory_number}: {e}")
            self.__error()
            return None

    def read_memory(self, 
                     memorie_adress:PLCAddress,
                     buffer:Buffer
                     ) -> None | bool:
        try:
            if not self.is_connected():
                return None

            BIndex = memorie_adress[0]
            bIndex = memorie_adress[1]

            if settings.DEBUGGING:
                print(f"Extrayendo M{BIndex * 8 + bIndex + 1} del buffer de memorias.")

            return buffer[BIndex][bIndex]

        except Exception as e:
            print(f"Error leyendo memoria: {e}")
            self.__error()
            return None

    def read_buffer_memories(self,
                             bytes_to_read:int=settings.MEMORIE_BYTES_READ
                             ) -> None | Buffer:
        try:
            if not self.is_connected():
                return None

            memories_state = [[False for _ in range(8)] for _ in range(bytes_to_read)]
            data = self.client.read_area(Areas.MK, 0, 0, bytes_to_read)

            for byteIndex in range(bytes_to_read):
                memories_state[byteIndex] = [get_bool(data,  byteIndex, bitIndex) for bitIndex in range(8)]

            return memories_state

        except Exception as e:
            print(f"Error leyendo memorias: {e}")
            self.__error()
            return None


#   --------------FUNCIONES DE BAJO NIVEL--------------#

    def get_length_data(self, memory:MemoryBlock) -> int:
        if memory.length == "word":
            return 2

        if memory.length == "dword":
            return 4

        return 1 #Byte

    def write_VM(self, values:list[int], data_zone:dict):
        """Para escribir el tiempo directamente en el LOGO! simplemente es coger la dirección del DB donde está almacenado el dato de edición 
        de tiempo de cada zona y se convierte el valor en segundos a hexadecimal y se escribe el valor. Hay que tener en cuenta la conversión
        de little endian a big endian, ya que el PLC trabaja en big endian."""

        if not self.is_connected():
            return None

        values = self.check_overflow(values)
        bytes_index = list(data_zone.keys()) #{"zona": {"byte": "tipoDato"}}
        
        if len(values) != len(bytes_index):
            print(f"Tiene que haber un valor para cada byte\nNº Bytes: {len(bytes_index)} | Nº Valores: {len(values)}")
            return 

        for i in range(len(values)):
            byte = int(bytes_index[i])
            value = values[i]
            
            data_length = self.get_length_data(data_zone, byte)
            self.client.write_area(Areas.DB,0,byte,(value).to_bytes(data_length, "big")) #EDIT: No, no se está usando little endian, al final es big. ||||| Igual sí que estoy usando aquí little endian y no me estoy enterando pero bueno, el tema es que va
            
            # client.write_area(Areas.DB,0,4,b'\x02') 
        return None
