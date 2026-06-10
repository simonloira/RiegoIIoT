# Índice:
<details>
  <summary>Expandir contenidos</summary>
  
  - [Breve descripción](#breve-descripción)
  - [Estructura del proyecto](#estructura-del-proyecto)
  - [Requisitos](#requisitos)
  - [Instalación](#instalación)
  - [Configuración](#configuración)

</details>

## Breve descripción
Este proyecto tiene como objetivo modernizar un sistema de riego existente convirtiéndolo en un sistema IIoT, la parte industrial recae en el uso del mini-PLC LOGO! Siemens ya que protege la bomba hidráulica que suministra el agua para poder regar. <br>
Para el control automático del riego y gestionar el consumo de agua no se instalarán sensores físicos por lo que, para obtener la información meteorológica, se emplearán dos APIs climáticas: Aemet (predicción) y las estaciones meteorológicas de Meteogalicia (información actual).

### Hardware
El hardware encargado de la lógica del sistema se compone de los siguientes dispositivos:
- **Raspberry Pi Zero 2W**: Actúa como puente entre el usuario final y el PLC.
  + Aloja la página web con la que interactúa el usuario.
  + Consigue la información climatológica y la almacena en una base de datos SQL.
  + Dependiendo de las condiciones climatológicas, controla la activación del riego en modo automático.  |[Explicación](/docs/diagramas.md#decisión-riego)|
  + Se encarga de la comunicación bidireccional entre el usuario y el PLC mediante el protocolo websocket.
  + Mediante una red privada Tailscale, permite interactuar con el sistema desde fuera de la red local.  |[Diagrama](/docs/diagramas.md#diagrama-de-red)|

<br>

- **LOGO! Siemens**: Se encarga de activar las electroválvulas y gestionar la bomba hidráulica.  |[Programa](/logo-plc/DocumentaciónProgramaLOGO.pdf)|[Esquema](/docs/esquema-eléctrico.pdf)|
  + Tiene su propia lógica interna, es decir, no depende de la Raspberry para funcionar.
  + En caso de desconexión con el servidor, se riega los días configurados durante un tiempo determinado. Ambos parámetros se pueden configurar desde la pantalla del LOGO! Siemens.
  + Protege la bomba contra varios arranques en un corto periodo. Además de contra el trabajo en vacío, gracias a un interruptor de nivel ubicado en el interior del pozo.
  + Permite visualizar diversos parámetros de funcionamiento: tiempo de riego por zonas, números de arranques de la bomba, estado del servidor, entre otros.
  + En caso de que los contactos del contactor que activan la bomba se suelden, se bloquea el funcionamiento hasta que se cambia el contactor; protegiéndola contra un funcionamiento continuo.

## Estructura del Proyecto
```
RiegoIIoT/
├── main.py                 # Punto de entrada de la aplicación y ciclo de vida
├── vars.env                # Variables de entorno (no incluídas en este repositorio)
├── load_var_env.py         # Carga las variables de entorno
├── settings.py             # Configuración global, IPs y rutas
├── logo-plc/               # Programa en LOGO! Soft Comfort
├── server/
│   ├── routes_pages.py     # Rutas para servir el frontend
│   ├── routes_ws.py        # Comunicación bidireccional entre el PLC y el frontend
│   └── tasks.py            # Tareas asíncronas (obtención del clima, watchdog y heartbeat del PLC)
├── backend/
│   ├── basics/             # Archivos auxiliares
│   ├── clima/              # Extracción y procesamiento de datos climáticos
│       └── datos_clima/    # Contiene los datos obtenidos de la APIs
│   ├── crud/               # Gestión de la base de datos
│   ├── history/            # Historial de activaciones y usuarios
│   ├── login/              # Inicio de sesión
│   └── PLC/                # Comunicación y control del PLC
│       └── config/         # Archivos JSON con mapeo de memorias y zonas
└── frontend/               # Archivos CSS, HTML, JS e imágenes.
```

## Requisitos 
1. Tener instalado Python3
<p> Para probar el sistema al completo:</p>

2. Contar con un mini-PLC LOGO! 8.4 y LOGO!Soft Comfort.
3. Cargar el programa al PLC.

## Instalación
1. Clonar este repositorio y acceder al directorio del proyecto: 
```bash
   git clone https://github.com/simonloira/RiegoIIoT.git
   cd RiegoIIoT
```
2. Crear el entorno virtual:
   - Linux/Mac: `python3 -m venv venv`
   - Windows: `py -m venv venv`
3. Activar el entorno virtual:
   - Linux/Mac: `source ./venv/bin/activate`
   - Windows: `.\venv\Scripts\activate`
4. Instalar los requisitos: `pip install -r requirements.txt`
   
## Configuración
1. Añadir las variables de entorno.
   - Crear en la raíz del proyecto el archivo: `vars.env`
   - Escribir dentro del archivo creado:
      ```
      METEOGALICIA_API_KEY = Clave de la API de meteogalicia
      USER_LOGIN = Nombre de usuario
      PASSWORD_LOGIN = Contraseña
      SECRET_JWT_KEY = Clave token JWT
      ```
2. Revisar los ajustes del servidor en `settings.py`. Por ejemplo:
   - Revisar la IP del LOGO!, el TSAP local y remoto o los bytes a leer del PLC.
3. Ejecutar el servidor:
   - Linux/Mac: `python3 -m main`
   - Windows: `python main.py`
4. El servidor estará funcionando en <http://localhost:8000> o en tu-ip-local:8000.

> En caso de tener el PLC:

5. Si no se modificó la IP preconfigurada en este proyecto para el PLC, se debe de conectar al servidor por ethernet y configurar la IP ethernet del servidor con la siguiente IP:

   ```bash
      IP: 192.168.2.2
      MÁSCARA: 255.255.255.0
   ```
   
6. Si se quiere controlar el sistema desde fuera de la red local, es recomendable configurar Tailscale.
