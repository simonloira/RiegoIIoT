from os import environ, path 

def load_vars_env(vars_env_path:str='vars.env') -> None:
    """ Lee el archivo que contiene las variables de entorno y las carga
        en ram (os.environ)

        Args:
            vars_env_path (str, optional): Ubicación del archivo con las 
            variables de entorno Defaults to 'vars.env'.
    """
    if not path.exists(vars_env_path):
        print(f'No existe en la raíz del proyecto el archivo: {vars_env_path}.')
        return
    with open(vars_env_path, "r", encoding='UTF-8') as file:
        for line in file.readlines():
            if not line or line.startswith("#"):
                continue
            key, value = line.replace('\n', '').split('=', 1)
            environ[key.strip()] = value.strip()