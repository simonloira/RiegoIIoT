from json import dumps, load
from os import path
from pathlib import Path
from typing import Any


def load_json_file(json_path: Path|str) -> dict[str, Any]:
    if path.exists(json_path):
        try:
            with open(json_path, "r", encoding="UTF-8") as f:
                content: dict[str, Any] = load(f)

                return content

        except Exception as e:
            print(f"Error cargando información del JSON ({json_path}): {e}")

    return {}


def save_json_file(
    file_name: str, json_path: str, data: dict[Any, Any] | list[Any] | str
) -> None:

    with open(json_path, "w", encoding="UTF-8") as file:
        file.write(f"\n{dumps(data)}")

    print(f"\nGuardado: {file_name}\nEn {json_path}.\n")
