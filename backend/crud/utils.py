
import sqlite3
from datetime import datetime, timedelta
from logging import getLogger

from settings import settings

logger = getLogger(__name__)

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
    PATH = settings.CLIMATE_DATA_PATH / "meteogalicia" / "meteogal.db"
    cx = sqlite3.connect(PATH)
    cu = cx.cursor()
    columns = ', '.join(SCHEME_TABLES['climate_data'])
    cu.execute(
        f"create table if not exists climate_data({columns})"
    )


def get_accumulated_rain_grass() -> float|None:
    PATH = settings.CLIMATE_DATA_PATH / "meteogalicia" / "meteogal.db"
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    current_hour = now.strftime('%H:%M:%S')
    yesterday = (now + timedelta(days=-1)).strftime('%Y-%m-%d')

    dates = [
        {"day": yesterday, "max_hour": "23:59:59"},
        {"day": today, "max_hour": current_hour}
    ]

    accum_rain:float|None = None
    for date in dates:
        window = f"'{date["day"]} {date["max_hour"]}'"
        s = f"timestamp >= '{date["day"]} 00:00:00' AND timestamp <= {window}"

        with sqlite3.connect(PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                f"SELECT * FROM climate_data WHERE {s} ORDER BY id DESC;"
            ).fetchone()
            if row is None:
                continue
            rain_day = row['accum_rain']
            logger.debug(
                f"{date["day"]} 00:00:00-{date["max_hour"]}: {rain_day} mm"
            )
            if accum_rain is None:
                accum_rain = rain_day
                continue

            accum_rain += row['accum_rain']

    return accum_rain



if __name__ == "__main__":
    print(get_accumulated_rain_grass())
