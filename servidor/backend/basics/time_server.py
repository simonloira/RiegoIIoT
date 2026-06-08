
# Este archivo realmente fue más por aprendizaje que por utilidad como tal
# porque ya existe la librería "datetime" que hace lo mismo y con más flexibilidad
# pero me apetecía pensar cuál es la lógica que hay detrás de una librería como esa.
from typing import Final


UTC_SPAIN = 2 #Cambiar el último domingo de marzo, por UTC+2 y el último domingo de octubre por UTC+1.
              # Próximo cambio: 29/03/2026 A ver si ya se acaban los cambios horarios en 2026.


def seconds_to_hour(total_seconds:float):
    hour = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    return hour, minutes, seconds


class GetDate():
    def __init__(self) -> None:
        self.INIT_YEAR: Final[int] = 1970 #UNIX epoch empieza en 1/1/1970 (0s)
        self.NAMES_MONTH: Final[list[str]] = \
        ["En.", "Feb.", "Marzo", "Abr.", "Mayo", "Jun.", "Jul.", "Ag.", "Sept.", "Oct.", "Nov.", "Dic." ]

    def is_leap(self, year:int) -> bool:
        return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

    def __get_year(self, seconds:float) -> tuple[int, float, bool]:
        """
        ### Calcula el año actual y los días restantes a partir de segundos UNIX.

        #### Args:
                **seconds** (float): UNIX timestamp

        #### Returns:
                tuple[int, float, bool]: Contiene:
                    - **count_year** (int): Número del año transcurrido desde 1970
                    - **days** (float): Días restantes del año actual en formato decimal.
                    - **is_leap** (bool): Indica si el año actual es bisiesto.
        """
        days_400_y = (400*365) + 100 - 3
        days_1970_now = seconds / 86400

        blocks = days_1970_now // days_400_y #Bloques de 400 años
        remaining_days = days_1970_now % days_400_y #Días restantes para alcanzar 400 años

        days_secule = (100*365) + 25 - 1
        secules = remaining_days // days_secule
        remaining_days = remaining_days % days_secule

        quad_days = (365 * 4) + 1
        quaddreniums = remaining_days // quad_days
        remaining_days = remaining_days % quad_days

        year = int((remaining_days // 365) + (quaddreniums * 4) + (secules * 100) + (blocks * 400))
        remaining_days = remaining_days % 365

        return year, remaining_days, self.is_leap(year)

    

    def __get_month(self,
                    remaining_days:float,
                    is_leap:bool) -> tuple[str, float, int]:
        """
        ### Calcula el mes actual y las horas restantes.

        #### Args:
            **curr_year_days** (float): Número de días para llegar a la fecha actual.
            **is_leap** (bool): Si es True es bisiesto si es False no es bisiesto

        #### Returns:
            tuple[str, float, int]: Contiene:
                - **months[month_count]** (str): Nombre del mes actual.
                - **remaining_days** (float): Resto del día en decimal(0.xx).
                - **month_count** (int): Número del mes actual.
        """
        days_month: list[int] = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        month_count = 0 #Mes actual

        if is_leap:
            days_month[1] = 29 #Febrero tiene 29 días si es bisiesto
        
        while remaining_days >= days_month[month_count]:
            remaining_days -= days_month[month_count]
            month_count += 1

        if month_count == 12:
            month_count = 0
        
        return self.NAMES_MONTH[month_count], remaining_days, month_count

    def __format_time(self, h:int, m:int, s:int) -> str:
        return f"{h:02d}:{m:02d}:{s:02d}"

    def __get_hour_mins_secs(self,
                             remaining_day:float) -> str:
        """
        ### Calcula la hora, minutos y segundos actuales.

        #### Args:
                **remaining_day** (float):Tiempo restante del día en formato decimal.

        #### Returns:
                str: Hora formateada en hh:mm:ss
        """
       
        total_seconds = remaining_day * 86400
        hour, minutes, seconds = seconds_to_hour(total_seconds=total_seconds)

        return self.__format_time(hour, minutes, seconds)
    
    def __delta_days(self,
                     day:int,
                     month:int,
                     year:int,
                     days_offset:int) -> tuple[int, 
                                               tuple[int, str],
                                               int]:
        """
        ### Añade días extra a una fecha pasada en los parámetros de la función

        #### Args:
                **day** (int): Número del día
                **month** (int): Número del mes
                **year** (int): Número del año
                **days_offset** (int): Días extra

        #### Returns:
                tuple[int, tuple[int, str],int]: (día, (mes, nombre del mes), año)
        """
        # Hay un bug que no urge solucionar porque realmente sólo se usa
        # para un offset de 1 día. Porque esta función sólo se usa para
        # conseguir los datos de la lluvia que hubo en 24 horas en meteogalica.
        # Pero bueno, el bug es que por cada año bisiesto hay un desfase de 1 día.
        DAYS_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        
        day += days_offset
        while day > DAYS_MONTH[month]:
            day -= DAYS_MONTH[month]
            month += 1
            if month > 11:
                month = month%12
                year += 1
            
        return day, (month, self.NAMES_MONTH[month]), year + self.INIT_YEAR
    
    def get_current_date(self,
                         seconds:float,
                         utc_time:int=UTC_SPAIN,
                         days_offset:int=1) -> tuple[tuple[int, tuple[int, str], int],
                                                     tuple[int, tuple[int, str], int],
                                                     str]:
        """ 
            ### Convierte una UNIX epoch en una fecha sin formato y hora formateada en: HH:MM:SS \
               también añade días a la fecha actual.

            #### Args:
                    **seconds** (float): UNIX epoch
                    **utc_time** (int, optional): Horario UTC. Defaults to UTC_SPAIN(UTC+1/UTC+2).
                    **days_offset** (int, optional): Días a añadir a la fecha actual. Defaults to 1.

            #### Returns:
                    tuple[tuple[int, tuple[int, str], int], tuple[int, ...], str]: (día, (número del mes, nombre del mes), año),
                    (día_offset, (mes_offset, nombre del mes_offset), año_offset), hora formateada en HH:MM:SS)
        """
        seconds = seconds + (3600 * utc_time)
        year, days, is_leap = self.__get_year(seconds)
    
        month_name, days,  month_idx= self.__get_month(remaining_days=days, is_leap=is_leap)
        day = int(days) + 1

        
        return  (
                    (day, (month_idx, month_name), year + self.INIT_YEAR), 
                    self.__delta_days(day, month_idx, year, days_offset), 
                    self.__get_hour_mins_secs(remaining_day= days % 1)
                )
       