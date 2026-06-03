from backend.clima.weather_data_extractor import WeatherMain

type WeatherExtractor = WeatherMain

get_weather: WeatherMain | None = None

def get_weather_extractor() -> WeatherMain:
    assert get_weather is not None, "No se inicializó la extracción del clima"
    return get_weather
