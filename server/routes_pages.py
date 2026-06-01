from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from backend.login.secure_token import check
import backend.history.history_manager as history_manager
from backend.clima.climate_flags import current_sky_status, current_temperature
from backend.login.login import check_login
from backend.login.secure_token import check, gen_payload, generate_token
from server.models import HistoryResponse, LoginRequest, MessageResponse
from settings import settings

router = APIRouter()
templates = Jinja2Templates(directory="./frontend/templates")
check_token = check()


async def validate_token(request: Request) -> bool:
    token = request.cookies.get("auth_token")
    if token and check_token.check_signature(token):
        return True
    return False


@router.get("/", response_class=HTMLResponse)
async def serve_page(request: Request,
                     valid_token: Annotated[bool, Depends(validate_token)]
                     ) -> HTMLResponse:
    if valid_token:
        return templates.TemplateResponse("index.html", {"request": request})
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/prevision", response_class=HTMLResponse)
async def read_item(request: Request):
    context = weather_manager.get_weather.read_last_saved_data(apis=["aemet", "meteogalicia"]) #[["aemet_7d", "aemet_h"], ["meteogalicia"]]
    context = {"aemet_7d": context[0][0], "aemet_h": context[0][1], "meteogalicia": context[1][0],
               "sky_status_index_day": current_sky_status(aemet_h=context[0][1]),
               "current_temperature": current_temperature(meteogalicia=context[1][0])}
    
    return templates.TemplateResponse(
        request=request, name="weather_bueno.html", context=context
    )


@router.get("/historial", response_class=HTMLResponse)
async def render_history(request: Request)-> HTMLResponse:
    return templates.TemplateResponse(
        request=request, name="history.html"
    )


@router.post("/login")
async def login_for_access_token(
    form_data:LoginRequest,
    response:Response) -> MessageResponse:
    success = check_login(form_data.username, form_data.password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario y/o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = gen_payload()

    token = generate_token(payload=access_token)
    #TODO: REFRESH TOKEN en vez de simplemente aumentar el tiempo
    response.set_cookie(key="auth_token", value= token, 
                        samesite="strict", httponly=True,
                        max_age=settings.ACCESS_TOKEN_MINUTES*60)

    return MessageResponse(message="Se ha inicidado sesión")


@router.get("/history-data")
async def read_history_data(request: Request,
                            valid_token: Annotated[bool, Depends(validate_token)]
                            )-> HistoryResponse:
    if valid_token:
        return HistoryResponse(history=history_manager.history_handler.history)
    raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No iniciaste sesión",
            headers={"WWW-Authenticate": "Bearer"},
        )


