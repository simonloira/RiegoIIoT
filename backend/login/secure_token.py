from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import sha256
from hmac import compare_digest, new
from json import dumps, loads
from time import time as actual_seconds
from typing import Any

from settings import settings  # type:ignore


def gen_payload() -> dict[str, float]:
    payload_default = {
        "iat": actual_seconds(),  # momento en que se solicita
        "expires": actual_seconds()
        + settings.ACCESS_TOKEN_MINUTES * 60,  # token disponible durante 2 horas
    }
    return payload_default


def base64url_encode(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def generate_token(
    payload: dict[str, float], header: dict[str, str] = {"alg": "HS256", "typ": "JWT"}
) -> str:  # Siempre va a ser el mismo header por defecto
    # Coniverto los diccionarios en json, los codifico en utf-8 y los codifico en base64url (sistema de codificación hmac)
    header_enc = base64url_encode(dumps(header).encode("utf-8"))
    params_en = base64url_encode(dumps(payload).encode("utf-8"))
    # Concateno el mensaje
    message = f"{header_enc}.{params_en}"
    # Genero la signature con la librería hmac, la signature es creada con el contenido (message) y con la clave secreta, para saber que el token se generó en el server
    signature = new(
        settings.SECRET_KEY.encode("utf-8"), message.encode("utf-8"), sha256
    ).digest()  # firma hmac

    return f"{header_enc}.{params_en}.{base64url_encode(signature)}"  # Token que se envía al cliente y se almacena en su localstorage


class check:  # Comprobar el token que se recibe desde el cliente
    def check_signature(self, client_token: str) -> bool:
        if client_token == None:
            return False
        # Añade padding (nº de "=" correspondiente para cumplir un grupo de 4 bits)
        print(client_token)
        self.raw_client_token = client_token
        self.client_token = client_token.split(".")
        self.client_token[1] += "=" * (-len(client_token[1]) % 4)

        try:
            if compare_digest(
                self.generate_probe_token(), self.raw_client_token
            ):  # Comprueba si el token generado es igual al token crudo recibido por el cliente (si se generó en este servidor o no)
                if (
                    actual_seconds() < self.maxtime
                ):  # Si no pasó el tiempo de expiración
                    print("Oleeeeee")
                    return True
                else:
                    print("Caducó la sesión")
                    return False
            else:
                print(
                    "No son iguales. Aunque deberían así que a ver qué pasa."
                )  # El token no se generó en el servidor ya que se usó otra clave secreta
                return False
        except Exception as e:
            print(e)
            return False

    def generate_probe_token(self) -> str:  # Genera el token de prueba
        content = (
            self.decode_content()
        )  # Decodifica el contenido legible (header y payload)
        self.maxtime = content[1][
            "expires"
        ]  # Se almacena el tiempo máximo de expiración en segundos desde el 1/1/1970

        return generate_token(
            header=content[0], payload=content[1]
        )  # Se genera el token según el contenido recibido desde el cliente

    def decode_content(self) -> list[Any]:  # Decodifica el contenido
        header = urlsafe_b64decode(self.client_token[0].encode("utf-8"))
        payload = urlsafe_b64decode(self.client_token[1].encode("utf-8"))

        return [
            loads(header),
            loads(payload),
        ]  # Devuelve el contenido a un formato json
