from datetime import datetime
from json import load
from os import getcwd

from backend.clima.models import AemetData, MeteoGaliciaData, CurrentWeatherData

PATH = getcwd()

def is_night(current_hour: int, sunriset_time:str, sunset_time:str) -> bool:
    sunrise_h = int(sunriset_time.split(":")[0])
    sunset_h = int(sunset_time.split(":")[0])

    if current_hour >= sunrise_h and current_hour <= sunset_h:
        return False
    return True

def get_day_hour_index(aemet_h):
    now = datetime.now()
    day_index:int
    hour_index:int
    
    for i in range(len(aemet_h["dia"])-1): 
        aemet_date = aemet_h["dia"][i]["@fecha"].split("-")
        if now.year == int(aemet_date[0]) and now.month == int(aemet_date[1]) and now.day == int(aemet_date[2]):
            day_index = i
            hour_index = now.hour - int(aemet_h["dia"][day_index]["estado_cielo"][0]["@periodo"]) 
            return day_index, hour_index
    return i, now.hour - int(aemet_h["dia"][i]["estado_cielo"][0]["@periodo"])

def current_sky_status(aemet_h:dict):
    #Los datos de aemet se componen de la sigueinte manera:
    #Es un diccionario con unas keys, dentro de esas keys existe la key "dia" que es una lista de diccionarios
    #cada elemento de esa lista representa la información climatológica de cada día "dia"[0] (hoy) "dia"[1] mañana, etc
    #Cada diccionario de cada dái tiene unas keys dentro de esas keys está la key "estado_cielo" que es una lista de
    #diccionarios cada diccionario tiene las keys ["@periodo"(hora), "@descripcion"(estado del cielo), "#text"(nombre icono)]

    day_index, hour_index = get_day_hour_index(aemet_h)

    # Hora actual - primera hora de los datos de day_index Por ejemplo: Igual la primera hora son las 00 o igual son las 9 pero aemet
    # siempre hace los informes antes de la hora actual o justo a la hora actual. Que me lleguen informes hechos después de la hora actual 
    # es físicamente imposible (todavía no se inventaron los viajes al futuro) y si aemet hace el informe tipo a las 9:42 la primera hora 
    # del day_index = 0 serían las 9:42  si day_index es 1 la primera hora serían las 00:00 porque sería el día siguiente.
    # Entonces, por eso "int(aemet_h["dia"][day_index]["estado_cielo"][0]["@periodo"])" nunca va a ser mayor que now.hour
    # Por lo que hour_index nunca será negativo y nunca se va a romper el código.
   
    status = aemet_h["dia"][day_index]["estado_cielo"][hour_index]["@descripcion"]

    night = is_night(datetime.now().hour, aemet_h["dia"][0]["@orto"], aemet_h["dia"][0]["@ocaso"])
    if night:
        status += " noche"

    with open(f"{PATH}/frontend/static/weather_icons/icons.json", encoding="UTF-8") as file:
        icon = load(file)[status]

    return status, icon, day_index, hour_index #Mando status: Estado cielo, icon: Icono del estado del cielo al lado de los grados
                                               #      day_index: Número del día de los datos de aemet para mostrar los datos de ese día
                                               #      hour_index: 

def current_temperature(meteogalicia:dict):
    temperature = float(meteogalicia["Temperatura"][1])
    dew_point = float(meteogalicia["Temperatura"][4])
    return round(temperature), round(dew_point)


