
from os import environ, path


def load_vars_env(vars_env_path:str='vars.env') -> None:
    """ Lee el archivo que contiene las variables de entorno y las carga
        en ram (os.environ)

        Args:
            vars_env_path (str, optional): Ubicación del archivo con las
             variables de entorno Defaults to 'vars.env'.
    """
    error = f'No existe en la raíz del proyecto el archivo: {vars_env_path}.'
    if not path.exists(vars_env_path):
        raise FileNotFoundError(error)

    with open(vars_env_path, "r", encoding='UTF-8') as file:
        for line in file.readlines():
            if line == '\n' or line.startswith("#"):
                continue
            line = line.split("#")[0].strip() #Comentarios en línea
            key, value = line.replace('\n', '').split('=', 1)
            environ[key.strip()] = value.strip()
