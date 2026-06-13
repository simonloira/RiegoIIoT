from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha256
from hmac import compare_digest, new
from json import dumps, loads
from logging import getLogger
from time import time as actual_seconds
from typing import Any

from settings import settings

logger = getLogger(__name__)

def gen_payload() -> dict[str, float]:
    payload_default = {
        "iat": actual_seconds(),  # momento en que se solicita
        "expires": actual_seconds()
        + settings.ACCESS_TOKEN_MINUTES
        * 60,  # token disponible durante 2 horas
    }
    return payload_default


def base64url_encode(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def generate_token(
    payload: dict[str, float],
    header: dict[str, str] = {"alg": "HS256", "typ": "JWT"},
) -> str:  # Siempre va a ser el mismo header por defecto
    # Coniverto los diccionarios en json, los codifico en utf-8 y los codifico
    # en base64url (sistema de codificación hmac)
    header_enc = base64url_encode(dumps(header).encode("utf-8"))
    params_en = base64url_encode(dumps(payload).encode("utf-8"))
    # Concateno el mensaje
    message = f"{header_enc}.{params_en}"
    # Genero la signature con la librería hmac, la signature es creada con el
    # contenido (message) y con la clave secreta, para saber que el token se
    # generó en el server
    signature = new(
        settings.SECRET_KEY.encode("utf-8"), message.encode("utf-8"), sha256
    ).digest()  # firma hmac

    # Token que se envía al cliente
    return f"{header_enc}.{params_en}.{base64url_encode(signature)}"


class check:  # Comprobar el token que se recibe desde el cliente
    def check_signature(self, client_token: str|None) -> bool:
        if client_token is None:
            return False
        # Añade padding (nº de "=" necesarios para cumplir un grupo de 4 bits)
        logger.debug("Token cliente: ", client_token)
        self.raw_client_token = client_token
        self.client_token = client_token.split(".")
        self.client_token[1] += "=" * (-len(client_token[1]) % 4)

        try:
            if compare_digest(
                self.generate_probe_token(), self.raw_client_token
            ):  # Comprueba si el token generado es igual al token crudo
                # recibido por el cliente (si se generó en este servidor o no)
                if (
                    actual_seconds() < self.maxtime
                ):  # Si no pasó el tiempo de expiración
                    logger.debug("Token correcto")
                    return True
                else:
                    logger.debug("Caducó la sesión")
                    return False
            else:
                logger.debug(
                    "No son iguales. Aunque deberían así que a ver qué pasa."
                )  # El token no se generó en el servidor ya que se usó otra
                   # clave secreta
                return False
        except Exception as e:
            logger.error(f"Error comprobando token {e}")
            return False

    def generate_probe_token(self) -> str:  # Genera el token de prueba
        # Decodifica el contenido legible (header y payload)
        content = (self.decode_content())
        # Se almacena el tiempo máximo de expiración en segundos desde 1/1/1970
        self.maxtime = content[1]["expires"]

        return generate_token(
            header=content[0], payload=content[1]
        )  # Se genera el token según el contenido recibido desde el cliente

    def decode_content(self) -> list[Any]:  # Decodifica el contenido
        header = urlsafe_b64decode(self.client_token[0].encode("utf-8"))
        payload = urlsafe_b64decode(self.client_token[1].encode("utf-8"))

        return [loads(header), loads(payload),]  # Devuelve en formato json
