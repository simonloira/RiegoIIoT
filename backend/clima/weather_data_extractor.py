import xmltodict
from dataclasses import dataclass, asdict
from json import loads, dumps, dump, load
from os import path
from requests import get, exceptions
from time import time, sleep
from typing import Dict, List, Tuple, Optional, Any

from backend.basics.time_server import get_date, UTC_SPAIN
from backend.basics.json_tools import load_json_file, save_json_file
from server.settings import settings as server_settings


@dataclass
class APIState:
    """Estado de las llamadas a la API"""
    last_fetch_time: float = 0
    next_retry_time: float = 0

    def __can_fetch(self, cache_ttl: int) -> bool:
        """Verificar si se puede hacer una nueva petición"""
        print(cache_ttl, self.last_fetch_time)
        print(f"Puede llamar? {(time() - self.last_fetch_time) > cache_ttl}")
        return (time() - self.last_fetch_time) > cache_ttl
    
    def __can_retry(self) -> bool:
        """Verificar si se puede reintentar"""
        print(f"Puede reintentar? {self.next_retry_time > 0 and time() > self.next_retry_time }")
        return self.next_retry_time > 0 and time() > self.next_retry_time 
    
    def can_call_or_retry(self, cache_ttl: int):
        return self.__can_fetch(cache_ttl) or self.__can_retry()


class GetMeteogaliciaData():
    def __init__(self):
        self.idstation = self.__read_ids_stations(f"{server_settings.MAIN_CLIMATE_PATH}/datos_clima/meteogalicia/IDStation.json")
        self.utc_offset = UTC_SPAIN # Corrección de hora. De meteogalicia se recibe UTC-(1 o 2 si invierno o no), 
                                    # mi clase (get_date()) hace la corrección a UTC0. Luego self.utc_offset hace 
                                    # la correción a UTC_SPAIN.

    def fetch_meteogalicia(self):
        try:
            # Se obtienen los datos climatológicos:
            filtered_data  = self.filter_raw_data() #->{"temperatura": [], "precipitación":[], "viento":[]..., "date":"{fecha actual=10 de Oct. de 2025, 21:47:21.}"}
            return [filtered_data] #Se devuelve una lista ya que se iteran los elementos que devuelve cada api. meteogalicia sólo devuelve uno
                                   # pero aemet devuelve 2 y se puede meter otra api que a lo mejor devuelva más.
        
        except Exception as e:
            print(f"Error obteniendo la información de meteogalicia {e}")
            return ""
    
    def filter_raw_data(self):
        raw_data = self.__get_raw_data()
        # Estructura de raw_data: Principales: ["BriefData", "lastData"]
        # Dentro de "lastData" hay diferentes elementos con disitintas keys. 
        # A mí sólo me interesa "name" ya que es el nombre de la magnitud medida (temperatura, viento, etc) y "lastData"
        # Dentro del "lastData" correspondiente a la magnitud medida hay datos distintos  de esa magnitud (Por ejemplo: temperatura ambiente y punto de rocío)
        # Cada "submagnitud" tiene los parámetros siguientes

        params = ["title", "value", "unit"] #Parámetros que me interesan de la información que me manda meteogalicia

        filtered_data = {}

        for i in range(len(raw_data["lastData"])):
            magnitude = raw_data["lastData"][i]["name"]
            filtered_data[magnitude] = []
            for j in range(len(raw_data["lastData"][i]["lastData"])):
                for value in params:
                    filtered_data[magnitude].append(raw_data["lastData"][i]["lastData"][j][value])
        
        if len(filtered_data) <= 3:
            return 

        #Se añade este campo para evitar errores en el renderizado en el html ya que da un error de jinja templates en el caso de que no exista la 
        #key de radiciaón solar. El problema es si hay otro parámetro que tiene la estación de cabo udra y otra estación no tiene ese parámetro,
        #vuelve a romperse el código. 
        #Es una solución temporal. Se mejorará en futuras iteraciones para hacerlo más robusto.
        if ("Radiación Solar" not in filtered_data.keys()):
            filtered_data["Radiación Solar"] = ["Radiación solar global", 0, "W/m2", "Horas de sol", 0,"h"]

        #Asignación de los valores de los demás parámetros
        filtered_data["date"] = get_date().get_current_date((raw_data["date"]/1000) + (3600 * self.utc_offset)) #Corrección a UTC_SPAIN
        filtered_data["estación"] = raw_data["station"]
        filtered_data["lluvia_acumulada"] = raw_data["accumulated_rain"]
        
        return filtered_data 

    def __get_raw_data(self) -> Dict:
        """ Esta función coge los datos crudos de meteogalicia, tal cual como llegan. Además también tiene que en cuenta que, a veces,
            puede ser que alguna estación no envíe datos. Entonces, se llama a la estación siguiente más cercana para ver si tiene datos; 
            si no tiene, coge los datos de la siguiente, y si ninguna tiene datos recientes (caso poco probable) se cogen los datos 
            más actualizados.
        """
        def get_accumulated_rain(id_station:str):
            print("Calculando lluvia acumulada del día")
            url_base = "https://apis-ext.xunta.gal/meteo2api/v1/api/graficas/datos/10minutal?idIntervalo=1&idGrafica=2&parametros=10001&"
            
            date = get_date().get_current_date(time(), hyphens_format=True, days_offset=1) #DD-MM-AA
            url = url_base + f"idEstacion={id_station}&fechaInicio={date[0]}%2000:10&fechaFin={date[1]}%2000:00"

            resp = get(url, headers=headers, timeout=5)
            data = resp.json().get("data", [])
            accumulated = sum(float(item["value"]) for item in data if float(item["value"]) >= 0)

            return ["Chuvia acumulada", round(accumulated,2), "L/m2"]
       
        
        most_updated_data = {}
        most_recent_date = 0 #0 es muy antiguo sería 01-01-1970
        
        for station, id in self.idstation.items():
            url = f"https://apis-ext.xunta.gal/meteo2api/v1/api/estacion-meteorologica/ultimos-datos?idEstacion={id}&idioma=gl"

            headers = {
                "apikey": "",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0"
            }

            try:
                resp = get(url, headers=headers, timeout=5)
                data = resp.json()
                print(f"Comprobando si {station} tiene datos actualizados")
                data_date = (data["date"] / 1000) + (3600 * self.utc_offset)

                if most_recent_date > data_date: #Si la fecha más reciente (datos más actualizados) es mayor que la fecha de los datos actuales, no son datos más actualizados.
                    print(f"Esta estación no tiene los datos más actualizados: {station}")
                    print(f"Fecha más reciente: {most_recent_date} Fecha de los datos: {data_date}\n")
                    sleep(2) #Se espera un tiempo para que Meteogalicia no reciba muschas solicitudes seguidas
                    continue

                most_recent_date = data_date
                most_updated_data = data
                most_updated_data["station"] = station
                most_updated_data["id_estation"] = id
                if (most_recent_date + 3600) > time(): #Sólo se permiten datos como máximo de hace una hora
                    print(f"{station} tiene datos actualizados")
                    break #Se termina el bucle para que no siga obteniendo datos de las demás estaciones ya que no es necesario
                sleep(2) #Se espera un tiempo para que Meteogalicia no reciba muschas solicitudes seguidas
            except exceptions.RequestException as error:
                print(f"Error llamando a meteogalicia {error}")
                return {}
        
        most_updated_data["accumulated_rain"] = get_accumulated_rain(most_updated_data["id_estation"])
        # print(f"\nDatos crudos de meteogalicia ({most_updated_data["station"]}): ", most_updated_data)
        return most_updated_data
    
    def __read_ids_stations(self, path:str):
        data = load_json_file(path)
        if data == {}:
            data = {"Cabo Udra": "10905"} #abo udra por defecto
        return data


class GetAemetData():
    def __init__(self):
        self.links = ["https://www.aemet.es/xml/municipios/localidad_36004.xml", 
                    "https://www.aemet.es/xml/municipios_h/localidad_h_36004.xml"]
        

        self.weather_params = [["@fecha", "estado_cielo", "prob_precipitacion", "uv_max", "temperatura"], 
                               ['@fecha', '@orto', '@ocaso', 'estado_cielo', 'precipitacion', 'temperatura', "sens_termica"]]

    def get_aemet(self) -> List:
        filtered_data = []
        
        for index, link in enumerate(self.links):
            weather_params = self.weather_params[index]
            selected_data = self.__call_aemet(weather_params = weather_params, 
                                            url = link)
            filtered_data.append(selected_data)
    
        return filtered_data

    def __call_aemet(self, weather_params:list, url:str) -> Dict: 
        try:
            xml_text = get(url, timeout=5).text

            selected_data = self.__select_data(weather_params = weather_params, 
                                            aemet_data = xmltodict.parse(xml_text))
            
            return selected_data
        except exceptions.RequestException as error:
            print(f"Error llamando a aemet {error}")
            return {}
    
    def __select_data(self, weather_params:list, aemet_data:dict):
        root_keys = ["elaborado", "nombre"]
        selected_data = {}
        
        for key in root_keys:
            if key in root_keys:
                selected_data[key] = aemet_data["root"][key]

        selected_data["dia"] = []
        for num_dia in range(len(aemet_data["root"]["prediccion"]["dia"])):
            day_dict = {}
            keys = aemet_data["root"]["prediccion"]["dia"][num_dia].keys()
            for key in weather_params:
                if key in keys:
                    day_dict[key] = aemet_data["root"]["prediccion"]["dia"][num_dia][key]
            selected_data["dia"].append(day_dict)

        selected_data["provincia"] = aemet_data["root"]["provincia"]
        return selected_data


class WeatherMain:
    def __init__(self):
        self.api_state: APIState #Se usa la misma variable para las dos apis
        self.time_retry: int 
        self.apis_config = load_json_file(server_settings.CONFIG_APIS_FILE_PATH)
        self.meteogalicia = GetMeteogaliciaData()
        self.aemet = GetAemetData()
        self.api_call_map = {"aemet": self.aemet.get_aemet, 
                             "meteogalicia": self.meteogalicia.fetch_meteogalicia}
        
    def read_last_saved_data(self, apis=["aemet", "meteogalicia"]):
        """Punto de entrada para conseguir los datos guardados previamente"""
        saved_data = []
        for api in apis:
            files_store_data = self.apis_config[api]["data_file_name"].keys()
            saved_data.append(self.__get_last_saved_data(api, files_store_data))
            print(f"Leída la información climatológica guardada de {api}\n")
        return saved_data
    
    def get_weather_data(self, apis=["aemet", "meteogalicia"]):
        """Función principal: 
            apis: Por defecto [aemet, meteogalica], si sólo se quiere obtener dartos de una api: ["aemet"]/["meteogalicia]
            Devuelve una lista: 
            True: En el websocket se permite enviar la información climatológica al cliente. Se pone a False en el websocket
            Data: Información climatológica."""
        
        if len(apis) == 0:
            assert "No se escogió una API correcta: [aemet, meteogalicia]"
        
        #Determina el tipo de escritura del archivo (añadir texto o sobrescribirlo). 
        save_mode_map = {} #Una vez ejecutado, por defecto pasaría a ser: save_mode_map={1:("7d","w"), "2":("h", "w"), "3": ("meteo", "a")}
        weather_data = []
        for api in apis:
            self.time_retry = self.apis_config[api]["time_retry"]
            self.cache_ttl = self.apis_config[api]["cache_ttl"]
            api_state_path = self.apis_config[api]["api_state_path"]

            print(f"\nProbando a llamar a {api}")
        
            #weather_data = lista que contiene los diccionarios que envía la API. Aemet manda 2 diccionarios, meteogal 1
            #save_mode_map = un diccionario con el nombre de cada archivo donde se guardará cada tipo de datos
            #de la API y su modo de guardado ({0: ("ejemplo.txt", "w")}
            save_mode_map, weather_data = self.__api_call_flow(api=api, 
                                                               api_state_path=api_state_path)

            for data_index, (file_name, save_mode) in save_mode_map.items():
                data_to_save = weather_data[data_index] #Weather_data empieza en 0
                data_already_saved = self.__check_saved_data(f"{api}/{file_name}", data_to_save)

                #Dependiendo de la api si no tiene info se manda una lista vacía (aemet) o con None dentro (meteogalicia)
                if not (data_to_save == None or weather_data == [None] or len(data_to_save) == 0) and not data_already_saved: 
                    self.__save_filt_climate_data(
                        file_path=f"{api}/{file_name}", 
                        data=data_to_save,
                        mode=save_mode
                    )
                    continue

                print(f"\n\nInfo ya guardada así que se guardará el tiempo para próximo intento {self.time_retry} {file_name}")
                self.api_state.next_retry_time = time() + self.time_retry
  
            self.__save_api_call_vars(api_state = self.api_state, 
                                      file_path = f"{server_settings.CLIMATE_DATA_PATH}/{api_state_path}")
            print(f"Obtenida la última información climatológica de {api}\n")
        
        return self.read_last_saved_data(apis=apis)  

    def __api_call_flow(self, api:str, api_state_path:str):

        save_mode_map = {}
        weather_data = [] #Datos de la API

        self.api_state = self.__load_api_call_vars(F"{server_settings.CLIMATE_DATA_PATH}/{api_state_path}")
    
        if not self.api_state.can_call_or_retry(self.cache_ttl): #Si se cumplió esta condición no se recibe nueva info climatológica
            print(api, " no puede llamar")
            return save_mode_map, weather_data
        
        #Se recibe nueva info climatológica
        weather_data = self.api_call_map[api]()
        
        #Memorizar el modo de guardado de la información climatológica en su archivo correspondiente (a: añadir texto, w: sobrescribir el archivo)
        #Si api = emet: save_mode_map={0:("7d","w"), "1":("h", "w")} 
        #Si api = meteogalicia: save_mode_map={0:("meteogalicia","a")} 
        for index, (key, value) in enumerate(self.apis_config[api]["data_file_name"].items()):
            save_mode_map[index] = (key, value)
            
        #Solución provisional para manejar la estructura de datos de Meteogalicia.
        #Ya que a la hora de guardar la información en su correspondiente archivo, se espera un array
        #Aemet devuelve un array que contiene dos diccionarios con su repectiva información (7d y h) 
        #pero meteogalicia sólo manda un diccionario,
        # if len(weather_data) != 2: 
        #     weather_data = [weather_data]

        self.api_state.last_fetch_time = time() #última llamada a la API = tiempo actuals
        return  save_mode_map, weather_data

    def __load_api_call_vars(self, file_path:str) -> APIState:
        """Cargar estado de la API desde archivo"""
        
        api_vars = load_json_file(file_path)
        # print(f"Estado de la API {api_vars}\n")
        if api_vars == {}:
            return APIState()
        
        return APIState(**api_vars)

    def __save_filt_climate_data(self, file_path:str, data:Dict[str,Any], mode="a"):
        ruta = f"{server_settings.CLIMATE_DATA_PATH}/{file_path}"

        if not path.exists(ruta):
            mode = "w"

        with open(ruta, mode, encoding="UTF-8") as file:
            file.write(f"\n{dumps(data)}")
        
        print(f"\nGuardado: {file_path}\nEn {ruta}.\n")

    def __check_saved_data(self, file_name:str, current_data:Dict): 
        saved_data = loads(self.__read_file(file_name)[-1])

        if saved_data == current_data:#Si ya está guardada la info climatológica se define el tiempo para reintentar otra llamada
            return True #Ya se guardó anteriormente esa información
        return False #No se guardó
    
    def __save_api_call_vars(self, api_state:APIState, file_path:str):
        """Guardar estado de la API en archivo"""
        
        try:
            
            with open(file_path, "w", encoding="UTF-8") as f:
                dump(asdict(api_state), f, indent=2)
        
        except Exception as e:
            print(f"Error guardando estado de API: {e}")
 
    def __read_file(self, file_name:str):
        ruta = f"{server_settings.CLIMATE_DATA_PATH}/{file_name}"
        
        if path.exists(ruta):
            with open(ruta, "r", encoding="UTF-8") as file:   
                data = file.readlines()
                if len(data) > 0:
                    return data
        
        no_data = {"nada": "nada"}
        return [dumps(no_data)]

    def __get_last_saved_data(self, api:str, files_names:List[str]):
        saved_data = []

        for file_name in files_names:
            saved_data.append(loads(self.__read_file(f"{api}/{file_name}")[-1]))

        return saved_data