from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from backend.clima.climate_flags import current_data
from backend.clima.models import APIs
from backend.clima.weather_manager import (
    WeatherExtractor,
    get_weather_extractor,
)
from backend.history.history_manager import HistorySave, get_history_saver
from backend.login.login import check_login
from backend.login.secure_token import check, gen_payload, generate_token
from server.models import (
    HistoryResponse,
    LoginRequest,
    MessageResponse,
    WeatherResponse,
)
from settings import settings

router = APIRouter()
templates = Jinja2Templates(directory="./frontend/templates")
check_token = check()


async def validate_token(request: Request) -> bool:
    token = request.cookies.get("auth_token")
    if token and check_token.check_signature(token):
        return True
    return False


def get_weather_data(weather: WeatherExtractor) -> WeatherResponse:
    weather_data = weather.read_last_saved_data(
        apis=[APIs.AEMET, APIs.METEOGALICIA]
    )
    aemet = weather_data.get("aemet")
    meteogalicia = weather_data.get("meteogalicia")
    if aemet is None or meteogalicia is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No hay información climatológica actualizada",
            headers={"Retry-After": "600"},  # reintentar en 10 minutos
        )
    current = current_data(aemet["hourly"], meteogalicia)
    return WeatherResponse(
        meteogalicia=meteogalicia, aemet=aemet, **current.model_dump()
    )


@router.get("/", response_class=HTMLResponse)
async def serve_page(
    request: Request, valid_token: Annotated[bool, Depends(validate_token)]
) -> HTMLResponse:
    if valid_token:
        return templates.TemplateResponse(name="index.html", request=request)
    return templates.TemplateResponse(name="login.html", request=request)


@router.get("/prevision")
async def render_forecast(
    request: Request,
    valid_token: Annotated[bool, Depends(validate_token)],
    weather: Annotated[WeatherExtractor, Depends(get_weather_extractor)],
) -> Any:
    if valid_token:
        return templates.TemplateResponse(
            name="weather_bueno.html",
            context={
                "request": request,
                **get_weather_data(weather).model_dump(),
            },
            request=request,
        )
    return RedirectResponse(url=request.url_for("serve_page"), status_code=303)


@router.get("/historial", response_class=HTMLResponse)
async def render_history(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="history.html")


@router.get("/forecast-data")
async def forecast_data(
    request: Request,
    weather: Annotated[WeatherExtractor, Depends(get_weather_extractor)],
) -> Response:
    #TTL de 10 mins para que no me haga muchas llamadas al servidor
    return Response(
        content=get_weather_data(weather).model_dump_json(),
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=600"},
    )


@router.post("/login")
async def login_for_access_token(
    form_data: LoginRequest, response: Response
) -> MessageResponse:
    success = check_login(form_data.username, form_data.password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario y/o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = gen_payload()

    token = generate_token(payload=access_token)
    # TODO: REFRESH TOKEN en vez de simplemente aumentar el tiempo
    response.set_cookie(
        key="auth_token",
        value=token,
        samesite="strict",
        httponly=True,
        max_age=settings.ACCESS_TOKEN_MINUTES * 60,
    )

    return MessageResponse(message="Se ha inicidado sesión")


@router.get("/history-data")
async def read_history_data(
    request: Request,
    valid_token: Annotated[bool, Depends(validate_token)],
    history_saver: Annotated[HistorySave, Depends(get_history_saver)],
) -> HistoryResponse:

    if valid_token:
        return HistoryResponse(history=history_saver.history)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No iniciaste sesión",
        headers={"WWW-Authenticate": "Bearer"},
    )
