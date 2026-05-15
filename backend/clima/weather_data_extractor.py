import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta
from json import dump, loads
from os import path
from pathlib import Path
from time import sleep, time
from typing import Any, cast

import xmltodict
from requests import exceptions, get

from backend.basics.json_tools import load_json_file
from backend.clima.models import (
    MAP_COMPLEX,
    MAP_SIMPLE,
    AemetData,
    AemetDayBase,
    AemetMagnitud,
    AemetPrediction,
    AllMagnitudeVariants,
    APIState,
    MagnitudData,
    MeteoGaliciaData,
    RawAemetData,
)
from settings import settings


class GetMeteogaliciaData():
    def __init__(self) -> None:
        self.meteogal_path = settings.CLIMATE_DATA_PATH / "meteogalicia"
        self.idstation = self._read_ids_stations(
            self.meteogal_path / "IDStation.json"
        )
        self.headers = {
                "apikey": settings.METEOGAL_API,
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
        # Meteogalicia manda los datos con un desfase extraño, es como si
        # internamente, el servidor de meteogalicia, restase dos horas
        # (o 1 dependiendo del horario) a UTC0 por lo que la única forma de que
        # corresponda con la hora local es con el offset manual
        #
        # El problema que le veo es que si meteogalicia corrige esto voy a
        # tener que tocar otra vez el código para esto.
        offset = datetime.now().astimezone().utcoffset()
        if offset:
            self.seconds_offset = offset.total_seconds()
        else:
            self.seconds_offset = 0 # Corrección de hora. De meteogalicia se
                                    # recibe UTC-(1 o 2 si invierno o no),
                                    # Luego self.utc_offset hace la correción
                                    # a UTC_SPAIN.

    def get_data(self) -> tuple[MeteoGaliciaData | None, bool]:
        """ Punto de entrada para llamar a meteogalicia.

            Returns:
                tuple[MeteoGaliciaData | None, bool]: Se compone por:
                    - MeteogaliciaData: Si el fetch fue bien, devuelve la
                    información guardada en RAM conseguida en el fetch. Si no,
                    devuelve la última información guardada en la base de datos
                    - None: Si hubo algún fallo de lectura en la base de datos.
                    - bool: Fallo en la llamada a la API.
        """
        data = self.__fetch_meteogalicia()
        fetch_failed = self.__save_data(data)
        return (data if data is not None else self.get_last_saved(),
                fetch_failed)

    def get_last_saved(self) -> MeteoGaliciaData | None:
        """Coge la última información guardada

        Returns:
            MeteoGaliciaData | None: Si hubo aǵun error de lectura devuelve
            None, si no devuelve la última información guardada de
            Metetogalicia.
        """
        with sqlite3.connect(self.meteogal_path/"meteogal.db") as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                          'SELECT * FROM climate_data ORDER BY id DESC LIMIT 1'
                            ).fetchone()

        if row is None:
            return None

        return MeteoGaliciaData(**{k: row[k] for k in row.keys() if k != "id"})

    def __save_data(self, data:MeteoGaliciaData|None) -> bool:
        """ Guarda la información en una base de datos SQLite y devuelve si
            hubo algún error.

            Args:
                data (MeteoGaliciaData | None): La información de meteogalicia.

            Returns:
                bool: Si hubo algún error y no se recibió información de
                meteogalicia o si la información actual es igual a la que está
                guardada devuelve True. Si fue todo bien devuelve False.
        """
        if data is None:
            return True

        with sqlite3.connect(self.meteogal_path/"meteogal.db") as conn:
            row = conn.execute(
                'SELECT id FROM climate_data WHERE timestamp = ?',
                (data.timestamp,)
            ).fetchone()
            if row:
                return True

            d = asdict(data)
            cols = ", ".join(d.keys())
            placeholders = ", ".join("?" * len(d))
            conn.execute(
                f'INSERT INTO climate_data ({cols}) VALUES ({placeholders})',
                list(d.values())
            )

        return False

    def __fetch_meteogalicia(self) -> MeteoGaliciaData | None:
        """ Punto de entrada para la llamada a Meteogalicia

            Returns:
                MeteoGaliciaData | None: Si se cayó meteogalicia o hubo algún
                error se devuelve None. Si fue todo bien se devuelve el objeto
                de la dataclass con los valores asignados.
        """
        try:
            # Se obtienen los datos climatológicos:
            raw_data: dict[str,Any] = self.__get_raw_data()
            #{"timestamp":"10 de Oct. de 2025, 21:47:21.", temp_15m:10.7, ...}
            filtered_data  = self.filter_raw_data(raw_data)
            return filtered_data
        except Exception as e:
            print(f"Error obteniendo la información de meteogalicia {e}")
            return None

    def filter_raw_data(self, raw_data: dict[str, Any]) -> (MeteoGaliciaData |
                                                            None):
        """ Filtra la información cruda que llega desde la API de meteogalicia
            y le asigna los valores a la dataclass MeteoGaliciaData

            Args:
                raw_data (dict[str, Any]): Informción cruda de meteogalicia

            Returns:
                MeteoGaliciaData | None: Si se cayó meteogalicia recibió un
                diccionario vacío, por lo que se devuelve None. Si fue todo
                bien se devuelve el objeto de la dataclass con los valores
                asignados.
        """
        if raw_data == {}:
            return None

        # Asignación de fecha y corrección a UTC_SPAIN
        ts = datetime.fromtimestamp(
                                    raw_data['date']/1000 + self.seconds_offset
                                   ).strftime("%d/%m/%Y, %H:%M:%S")

        accum_rain = self.__get_accumulated_rain(raw_data["id_estation"])

        data = MeteoGaliciaData(timestamp=ts,
                                station_id=raw_data['station'],
                                accum_rain = accum_rain)

        for magnitude in raw_data['lastData']:
            for param in magnitude['lastData']:
                p_id = param.get("idParam")
                f_id = param.get("idFunction")
                val = param.get("value", 0.0)

                if val is None:
                    val = 0.0

                attr = MAP_SIMPLE.get(p_id) or MAP_COMPLEX.get((p_id, f_id))

                if attr:
                    setattr(data, attr, val)
        return data

    def __get_accumulated_rain(self, id_station:str) -> float:
            """ Se calcula la lluvia acumulada mediante los valores que llegan
                de la gráfica diezminutal de lluvia de meteogalicia.

                Args:
                    id_station (str): Es un número en formato string,
                    corresponde al id de la base de datos de meteogalicia.
                    Está guardado en:
                    `backend/clima/datos_clima/meteogalicia/IDStation.json`

                Returns:
                    float: Cantidad de lluvia acumulada en el día de hoy
            """
            print("Calculando lluvia acumulada del día")

            ENDPOINT = "https://apis-ext.xunta.gal/meteo2api/v1/api/graficas/datos/10minutal"

            # Se obtiene la fecha de hoy y la fecha de mañana y se formatean a
            # una estructura compatible con el link para conseguir un link
            # válido y conseguir los valores desde las 00:10 de hoy y las 00:00
            # del día siguiente.
            now = datetime.now()
            dates = [now.strftime('%d-%m-%Y'), (now + timedelta(days=1)
                                                ).strftime('%d-%m-%Y')]
            params:dict[str, int|str] = {
                                            "idIntervalo": 1,
                                            "idGrafica": 2,
                                            "parametros": 10001,
                                            "idEstacion": id_station,
                                            "fechaInicio": f"{dates[0]} 00:10",
                                            "fechaFin": f"{dates[1]} 00:00"
                                        }

            resp = get(ENDPOINT, timeout=5,
                       headers=self.headers,  params=params)
            data = resp.json().get("data", [])

            accumulated = sum(float(item["value"]) for item in data if float(item["value"]) >= 0)  # noqa: E501

            return round(accumulated,2)

    def __get_raw_data(self) -> dict[str, Any]:
        """ Esta función coge los datos crudos de meteogalicia, tal cual como
            llegan. Además también tiene en cuenta que, a veces, puede ser que
            alguna estación no envíe datos. Entonces, se llama a la estación
            siguiente más cercana para ver si tiene datos  actualizados, si
            tiene datos igual de actualizados que la estación anterior, se
            queda con la anterior. Si no tiene, coge los datos de la siguiente.
            Si ninguna tiene datos recientes (algo raro, ya se tendrían que
            alinear los astros si se cae meteogalicia) se manda un diccionario
            vacío, aunque lo normal es que siempre mande datos. El único
            escenario donde no mandaría datos es si meteogalicia está caído
            porque daría timeout error en todas las peticiones por lo que
            most_updated_data se quedaría valiendo {}.

            Returns:
                dict[str, str| int | list[dict[str, str | int | list[dict[str,
                str | int]]]]]: Información cruda de la API
        """
        ENDPOINT = "https://apis-ext.xunta.gal/meteo2api/v1/api/estacion-meteorologica/ultimos-datos"
        #Pongo Any porque resp.json() devuelve Any, aunque la estructura
        #del json es la que tengo escrita como retorno de la función
        most_updated_data: dict[str, Any] = {}
        most_recent_date = 0 #0 es muy antiguo sería 01-01-1970

        for station, id in self.idstation.items():
            params:dict[str, int|str] = {"idEstacion": id, "idioma": "gl"}
            try:
                resp = get(ENDPOINT, timeout=5,
                           headers=self.headers, params=params,)
                data = resp.json()
                print(f"\nA ver si {station} tiene datos actualizados")
                # Se divide entre mil porque vienen en milisegundos y se aplica
                # el offset para corregirlo a UTC0 porque meteogalicia manda el
                # dato en UTC-2/UTC-1
                data_date = (data['date'] / 1000) + self.seconds_offset

                # Si la fecha más reciente (la de los datos más actualizados)
                # es mayor que la fecha de los datos actuales, no son datos
                # más actualizados.
                if most_recent_date > data_date:
                    print(f"{station}: no tiene los datos más actualizados")
                    print(f"Recientes: {most_recent_date}|Ahora: {data_date}")
                    continue
                elif most_recent_date == data_date:
                    print(f"{station} está igual de actualizado que: ",
                          most_updated_data['station'])
                    print("Por lo que me quedaré con los datos de: ",
                          most_updated_data['station'])
                    continue

                most_recent_date = data_date #Hora con datos más actualizados
                most_updated_data = data
                most_updated_data['station'] = station
                most_updated_data['id_estation'] = id

                #Sólo se permiten datos como máximo de hace una hora
                if (most_recent_date + 3600) > time():
                    print(f"{station} tiene datos actualizados")
                    break #No es necesario que llame a las demás estaciones
                sleep(0.5) #Para no enviar muchas solicitudes seguidas
            except exceptions.RequestException as error:
                print(f"Error llamando a meteogalicia: {error}")
                sleep(2) #Se espera un poco antes de volver a pedir
                continue

        return most_updated_data

    def __read_ids_stations(self, path:Path) -> dict[str, str]:
        """ Lee los ids de las estaciones. Están ordenadas en su archivo
            correspondiente de más póxima a más lejana.

            Args:
                path (str): Ruta del archivo json con los ids de las estaciones

            Returns:
                dict[str, str]: Nombre de la estación como key y el id en forma
                de string como value.
        """
        data = load_json_file(path)
        if data == {}:
            data = {"Cabo Udra": "10905"} #Cabo udra por defecto
        return data


class GetAemetData():
    def __init__(self) -> None:
        self.links = {'7d': "https://www.aemet.es/xml/municipios/localidad_36004.xml",
                      'hourly':"https://www.aemet.es/xml/municipios_h/localidad_h_36004.xml"}

    def get_data(self) -> tuple[dict[str, AemetData], bool]:
        """Punto de entrada para llamar a Aemet.

         Returns:
            tuple[dict[str, AemetData], bool]: Información de Aemet y fallo
            guardando la información
        """
        new_data = self._fetch()
        failure, message = self._save(new_data)
        print(message)

        # Solo lee de disco si falló, si no usa lo que ya tiene en RAM
        final_output: dict[str, Any] = {}
        for key in self.links.keys():
            if new_data.get(key) is not None:
                final_output[key] = new_data[key]
            else:
                cached = self._read_file(f"{key}.json")
                final_output[key] = loads(cached[-1]) if cached else {}
        return final_output, failure

    def get_last_saved(self) -> dict[str, Any]:
        """ Lee la última información guardada, se usa en WeatherMain cuando
            comprueba que aemet no puede llamar

            Returns:
                dict[str, Any]: Información de Aemet.
        """
        final_output: dict[str, Any] = {}
        for key in self.links.keys():
            cached = self._read_file(f"{key}.json")
            if cached:
                final_output[key] = loads(cached[-1])
            else:
                final_output[key] = {}
        return final_output

    def _read_file(self, file_name:str) -> list[str] | None:
        """Lee el archivo de Aemet (7d o hourly)

        Args:
            file_name (str): Nombre del archivo (7d, hourly)

        Returns:
            list[str] | None: Devuelve las líneas que leyó del archivo
        """
        path_file = Path(settings.CLIMATE_DATA_PATH/'aemet'/file_name)

        if not path.exists(path_file):
            return None

        with open(path_file, "r", encoding="UTF-8") as file:
            data = file.readlines()
            if len(data) > 0:
                return data
            return None

    def _save(self,
               data:dict[str, AemetData | None]
               ) -> tuple[bool, str]:
        """Sobrescribe un archivo txt para guardar la información de Aemet.

        Args:
            data (dict[str, AemetData | None]): Información de Aemet

        Returns:
            tuple[bool, str]: Error guardando ya que no había información para
            guardar y mensaje de archivos en los que se puedo guardar y en los
            que no.
        """
        ruta = Path(settings.CLIMATE_DATA_PATH/"aemet")

        file_paths:list[Path] = []
        no_data_paths: list[Path] = []
        failure = False
        for key in data.keys():
            file_path = Path(ruta/f'{key}.json')

            d = data[key]
            if d is None:
                no_data_paths.append(file_path)
                failure = True
                continue

            with open(file_path, "w", encoding="UTF-8") as file:
                dump(asdict(d), file)

            file_paths.append(file_path)

        return (failure,
               f"\nGuardados: {file_paths}.\n Conflictivos:{no_data_paths}")

    def _fetch(self) -> dict[str, AemetData | None]:
        """Punto de entrada para llamar a Aemet

        Returns:
            dict[str, AemetData | None]: Información de Aemet.
            Sigue la siguiente estructura:
            `{"7d": "info de 7d", "hourly": "info de hourly"}`
        """

        filtered_data:dict[str, AemetData | None] = {}

        for key in self.links.keys():
            selected_data = self._call_aemet(url = self.links[key])
            filtered_data[key] = selected_data

        return filtered_data

    def _call_aemet(self,url:str) -> AemetData | None:
        """ Llama a Aemet para conseguir la información cruda de un tipo de
            dato (7d o hourly). La información se obtiene parseando un xml.

            Args:
                url (str): Enlace para conseguir el xml de 7d/hourly.

            Returns:
                dict[str, str | list[dict[str, Any]]] | None: Información cruda
                de 7d/hourly.
        """
        try:
            xml_text = get(url, timeout=5).text
            parsed_data = xmltodict.parse(xml_text)
            selected_data = self._select_data(aemet_data = parsed_data)

            return selected_data
        except exceptions.RequestException as error:
            print(f"Error llamando a aemet {error}")
            return None

    def _select_data(self,
                     aemet_data:RawAemetData
                    ) -> AemetData:
        """ Se filtra la información cruda y se normaliza ya que Aemet se
            recibe desde Aemet un JSON  no normalizado, lo que dificulta el
            filtrado y el tipado estático.

            Args:
                aemet_data (RawAemetData): Información cruda del xml de aemet
                parseado.

            Returns:
                AemetData: Información filtrada de cada tipo de dato: 7d/hourly
        """
        days:list[AemetDayBase] = []
        root = aemet_data['root']
        prediction:AemetPrediction = cast(AemetPrediction, root['prediccion'])

        for day in prediction['dia']:
            max_temp = None
            min_temp = None
            rain = day.get('precipitacion') or day.get('prob_precipitacion')
            temp_data = day.get('temperatura')

            if isinstance(temp_data, dict):
                max_temp = self._s(temp_data, 'maxima')
                min_temp = self._s(temp_data, 'minima')
                temp_data = self._s(temp_data, 'dato')

            day_data_str = cast(dict[str, str], day)
            day_data = AemetDayBase(
                date=cast(str, self._s(day_data_str, '@fecha')),
                sunrise=cast(str, self._s(day_data_str, '@orto')),
                sunset=cast(str, self._s(day_data_str, '@ocaso')),
                uv_max=cast(str, self._s(day_data_str, 'uv_max')),
                max_temp=max_temp,
                min_temp=min_temp,
                temperature=self._parse_magnitud(temp_data),
                sky_status=self._parse_magnitud(day.get('estado_cielo')),
                rain=self._parse_magnitud(rain),
                therm_sense=self._parse_magnitud(day.get('sens_termica')),
            )

            days.append(day_data)

        root_str = cast(dict[str, str], root)
        data = AemetData(made_date=cast(str, self._s(root_str, 'elaborado')),
                         village=cast(str, self._s(root_str, 'nombre')),
                         province=cast(str, self._s(root_str, 'provincia')),
                         days = days)
        return data

    def _parse_magnitud(self,
                         magnitud_data:AllMagnitudeVariants
                         ) -> list[AemetMagnitud]:
        """ Filtra la información de las magnitudes

            Args:
                magnitud_data (AllMagnitudeVariants): Este tipo contiene todos
                las posibles estructuras que puede tener la información de cada
                magnitud. Generalmente la información suele venir en una lista
                de diccionarios de longitud igual a los periodos diarios, pero
                en los datos de predicción de 7 días, a medida que se llega a
                los últimos días de la predicción esta suele perder detalle,
                por lo que suelen venir en simplemente diccionarios o incluso
                strings (si el único periodo es de 00-24, aunque esto varía.
                Ya que a veces, dependiendo de la magnitud, también viene en
                diccionarios).

            Returns:
                list[AemetMagnitud]: Magnitud normalizada
        """

        periods:list[AemetMagnitud] = []

        if magnitud_data is None:
            return periods # Lista vacía para evitar errores de iteración

        items: list[MagnitudData]
        # Si es un diccionario (caso 7 días), se normaliza a lista
        if isinstance(magnitud_data, dict | str):
            items = [magnitud_data]
        else:
            items = magnitud_data

        for period in items:
            # Viene sin la key "@periodo". Es decir, items es una lista de
            # un sólo string viene con el valor que va a tener esa magnitud
            # todo el día.
            if isinstance(period, str):
                periods.append(AemetMagnitud(
                    hour="00-24",
                    value=period,
                    description=None
                ))
                continue
            # Si el periodo no tiene hora/periodo (es dato diario),
            # se le pone "00-24"
            hour = period.get('@periodo') or period.get('@hora') or "00-24"
            description = period.get('@descripcion')

            periods.append(AemetMagnitud(
                hour=hour,
                value=period.get('#text'),
                description=None if description == "" else description
            ))
        return periods

    def _s(self,
           d:dict[str, str],
           key:str,
           default: str| None = None
           ) -> str|None:
        return d.get(key, default)


class WeatherMain:
    def __init__(self) -> None:
        self.api_state: APIState #Se usa la misma variable para las dos apis
        self.time_retry: int
        self.apis_config = load_json_file(settings.CONFIG_APIS_FILE_PATH)
        self.meteogalicia = GetMeteogaliciaData()
        self.aemet = GetAemetData()
        self.api_call_map:dict[str, Any] = {
            "aemet": self.aemet.get_data,
            "meteogalicia": self.meteogalicia.get_data
        }
        self.retrieve_save_map:dict[str, Any] = {
            "aemet": self.aemet.get_last_saved,
            "meteogalicia": self.meteogalicia.get_last_saved
        }

    def get_weather_data(self,
                         apis:list[str]=["aemet", "meteogalicia"]
                         ) -> dict[str, Any]:
        """ Punto de entrada para obtener toda la información climatológica

            Args:
                apis (list[str], optional): Por defecto [aemet, meteogalica],
                si sólo se quiere obtener datos de una api:
                ["aemet"]/["meteogalicia]

            Returns:
                dict[str, Any]: Información de la apis junta en un diccionario.
                Sigue la siguiente estructura:
                `{'aemet': {info de aemet},
                  'meteogalicia': {info de meteogalicia}}`
        """

        if len(apis) == 0:
            raise ValueError("No se escogió una API correcta: [aemet, meteogalicia]")  # noqa: E501

        #Determina el tipo de escritura del archivo
        # (añadir texto o sobrescribirlo).
        full_data:dict[str, Any] = {}
        for api in apis:
            #Se recuperan los tiempos de llamada y de reintento de la API
            self.time_retry = self.apis_config[api]["time_retry"]
            self.cache_ttl = self.apis_config[api]["cache_ttl"]
            api_state_path = self.apis_config[api]["api_state_path"]

            print(f"\nProbando a llamar a {api}")

            api_data, fetch_failed = self.__api_call_flow(api=api,
                                                          api_state_path=api_state_path)

            if api_data is None:
                continue

            full_data[api] = api_data

            if fetch_failed:
                print("\n\nFalló el fecth o info ya guardada")
                print("Se guardará el tiempo para próximo intento: ",
                      self.time_retry, api)
                self.api_state.next_retry_time = time() + self.time_retry
            else:
                #última llamada a la API = tiempo actuals
                self.api_state.last_fetch_time = time()
                self.api_state.next_retry_time = 0

            vars_path = Path(settings.CLIMATE_DATA_PATH/api_state_path)
            self.__save_api_call_vars(api_state = self.api_state,
                                      file_path = vars_path)
            print(f"Obtenida la última información climatológica de {api}\n")

        print(full_data)
        return full_data

    def __api_call_flow(self, api:str, api_state_path:str) -> tuple[Any, bool]:
         """ Gestiona la llamada a la API.

            Args:
                api (str): Nombre de la API
                api_state_path (str): Valores de reintento y del tiempo hasta
                que se debe de volver a llamar a la API (TTL). Guardado en:
                `backend/clima/datos_clima/CLIMATE_APIS_CONFIG.json`

            Returns:
                tuple[Any, bool]: Devuelve la información de la API y si falló
                la llamada para gestionar asignar el tiempo de reintento.
        """
        path = Path(settings.CLIMATE_DATA_PATH/api_state_path)
        self.api_state = self.__load_api_call_vars(path)

        #Si se cumplió esta condición no se recibe nueva info climatológica
        if not self.api_state.can_call_or_retry(self.cache_ttl):
            print(f"{api} no puede llamar. Recuperando información guardada.")
            return self._read_last_data(api), False

        #Se recibe la info climatológica de la API
        api_data, fetch_failed = self.api_call_map[api]()

        return api_data, fetch_failed

    def _read_last_data(self,
                        api:str
                        ) -> MeteoGaliciaData | dict[str,AemetData] | None:

        data:MeteoGaliciaData | dict[str,AemetData] | None

        print("Recuperando información guardada...")
        data = self.retrieve_save_map[api]()
        if data == {} or (data is None):
            print("Error recuperando la información guardada.")
            return data
        print("Información recuperada.")
        return data
    def __load_api_call_vars(self, file_path:Path) -> APIState:
        """Cargar estado de la API desde archivo"""

        api_vars = load_json_file(file_path)
        if api_vars == {}:
            return APIState()

        return APIState(**api_vars)

    def __save_api_call_vars(self, api_state:APIState, file_path:Path):
        """Guardar estado de la API en archivo"""

        try:

            with open(file_path, "w", encoding="UTF-8") as f:
                dump(asdict(api_state), f, indent=2)

        except Exception as e:
            print(f"Error guardando estado de API: {e}")


if __name__ == "__main__":
    weather = WeatherMain()
    weather.get_weather_data()
