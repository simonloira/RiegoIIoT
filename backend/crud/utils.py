
import sqlite3
from settings import settings

SCHEME_TABLES = {
    "climate_data": [
        "id INTEGER PRIMARY KEY ",
        "timestamp STRING",
        "station_id STRING",
        "temp_15m REAL",
        "temp_dewpoint REAL",
        "hum_rel REAL",
        "last_rain REAL",
        "accum_rain REAL",
        "wind_speed REAL",
        "wind_gust REAL",
        "wind_dir REAL",
        "wind_gust_dir REAL",
        "solar_radiation REAL",
        "solar_hours REAL",
    ],
}


def create_meteogal_table() -> None:
    cx = sqlite3.connect(settings.CLIMATE_DATA_PATH / "meteogalicia" / "meteogal.db")
    cu = cx.cursor()
    cu.execute(
        f"create table if not exists climate_data({', '.join(SCHEME_TABLES['climate_data'])})"
    )
