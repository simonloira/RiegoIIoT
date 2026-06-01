from server.settings import settings as server_settings

import backend.login.secure_token as token_gen


def check_complete_login(data:dict):
    user = data.get("user")
    password = data.get("password")
    if user is None or password is None:
        print("Mensaje login incompleto:", data)
        return
    return check_login(user, password)

def check_login(input_user, input_password):
    login = read_login()
    user = login[0].replace("\n","")
    password = login[1].replace("\n","")
    print(input_user, input_password)
    if input_user == user and input_password == password:
        payload = token_gen.gen_payload()
        return [token_gen.generate_token(payload), True]
    
    return ["", False]

def read_login():
    with open(server_settings.LOGIN_PATH, "r", encoding="UTF-8") as file:
        return file.readlines()
