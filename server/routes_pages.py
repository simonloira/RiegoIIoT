from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.login.secure_token import check
import backend.clima.weather_manager as weather_manager
from backend.clima.climate_flags import current_sky_status, current_temperature

router = APIRouter()
templates = Jinja2Templates(directory="./frontend/static/templates")
# templates = Jinja2Templates(directory="./frontend/pruebas")
check_token = check()

@router.get("/", response_class=HTMLResponse)
async def serve_page(request: Request):
    token = request.cookies.get("auth_token")
    if token and check_token.check_signature(token):
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

