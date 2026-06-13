from json import dumps, load
from logging import getLogger
from os import path
from pathlib import Path
from typing import Any

logger = getLogger(__name__)

def load_json_file(json_path: Path|str) -> dict[str, Any]:
    if path.exists(json_path):
        try:
            with open(json_path, "r", encoding="UTF-8") as f:
                content: dict[str, Any] = load(f)
                logger.debug(f"Leído el archivo {json_path}")
                return content

        except Exception as e:
            logger.error(
                f"Error cargando información del JSON ({json_path}): {e}"
            )

    return {}


def save_json_file(
    file_name: str, json_path: str, data: dict[Any, Any] | list[Any] | str
) -> None:

    with open(json_path, "w", encoding="UTF-8") as file:
        file.write(f"\n{dumps(data)}")

    logger.debug(f"Guardado: {file_name}. En {json_path}.")
