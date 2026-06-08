from settings import settings


def check_login(input_user:str, input_password:str) -> bool:
    user = settings.USER
    password = settings.PASSWORD

    if input_user == user and input_password == password:
        return True
    return False
