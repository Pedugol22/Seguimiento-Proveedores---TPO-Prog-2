import os
import re
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv es opcional: sin él se usan solo variables de entorno
    pass


def _lista_desde_env(nombre):
    valor = os.environ.get(nombre, "")
    return [item.strip() for item in valor.split(",") if item.strip()]


# --- Parámetros HTTP (diccionario) ------------------------------------
PARAMETROS_HTTP = {
    "timeout": 15,
    "user_agent": "TP-UADE-Programacion2 (seguimiento de proveedores; uso academico)",
    "pausa_entre_pedidos": 2.0,   # segundos entre pedidos al mismo sitio
}

# --- Fuentes externas -------------------------------------------------
FUENTES = {
    "boletin_oficial": "https://www.boletinoficial.gob.ar",
    "bcra_deudores": "https://api.bcra.gob.ar/CentralDeDeudores/v1.0",
    # Servicio que usa la herramienta pública "Consulta de CUIT" de FactuARCA (datos de la constancia de ARCA).
    "padron_arca": "https://api.factuarca.app/v1/tools/padron",
}

# --- Listas de control (N05) --------------------------------------------
# Dominios desde los que el scraper tiene permitido descargar HTML: solo los sitios que se scrapean
# o consultan como API pública (el padrón de ARCA se consulta con su propio módulo, no con el scraper).
DOMINIOS_PERMITIDOS = sorted({urlparse(FUENTES[nombre]).hostname
                              for nombre in ("boletin_oficial", "bcra_deudores")})

# CUIT de proveedores críticos para la organización (se cargan desde el entorno, sin guiones).
# A un proveedor crítico se le aplica un criterio más estricto en la evaluación.
PROVEEDORES_CRITICOS = [re.sub(r"\D", "", cuit) for cuit in _lista_desde_env("PROVEEDORES_CRITICOS")]

# --- Estados documentales (N06) ------------------------------------------
# Cuánto aporta al cumplimiento documental cada estado de un documento (1 = cumple del todo).
ESTADOS_DOCUMENTALES = {
    "vigente": 1.0,
    "por_vencer": 0.5,
    "vencido": 0.0,
    "faltante": 0.0,
}

# --- Scraping: se puede desactivar por configuración -------------------
SCRAPING_HABILITADO = os.environ.get("SCRAPING_HABILITADO", "true").strip().lower() != "false"

# --- Credenciales (siempre desde el entorno) ---------------------------
# Claves que acepta NUESTRA API (se mandan en el header X-API-Key).
API_KEYS_VALIDAS = _lista_desde_env("API_KEYS")

# Clave que usa main.py para llamar a nuestra API.
API_KEY_CLIENTE = os.environ.get("PROVEEDORES_API_KEY", "")

# Dirección donde corre nuestra API.
API_URL = os.environ.get("PROVEEDORES_API_URL", "http://127.0.0.1:8000")

# Ruta opcional a un certificado CA propio si el BCRA da error de SSL en tu red.
# Si no se define, se usa la verificación normal de certificados.
BCRA_CA_BUNDLE = os.environ.get("BCRA_CA_BUNDLE") or True

# Destinatarios del comité (para la etapa de correo, más adelante).
DESTINATARIOS_COMITE = _lista_desde_env("COMITE_EMAILS")

# --- ETL con Pandas ---------------------------------------------------------
# Archivo CSV donde se guarda el ranking de proveedores.
ARCHIVO_CSV = os.environ.get("PROVEEDORES_CSV", "salidas/ranking.csv")

# Carpeta donde se guardan los Excel de cada consulta (está en .gitignore).
CARPETA_SALIDAS = os.environ.get("PROVEEDORES_SALIDAS", "salidas")


# --- Correo (SMTP) -------------------------------------------------------------
def _entero_desde_env(nombre, por_defecto):
    try:
        return int(os.environ.get(nombre, por_defecto))
    except ValueError:
        return por_defecto


def _sin_valor_de_ejemplo(valor):
    valor = valor.strip()
    return "" if valor.startswith("pone-aca") or valor.lower() == "tu_mail@gmail.com" else valor


# Cuenta DESDE la que sale el mail (la carga quien instala el programa, en el .env).
# Con Gmail: smtp.gmail.com, puerto 587 (STARTTLS) y una "contraseña de aplicación" (no la clave normal).
# El mail DE DESTINO no va acá: se escribe en la terminal en cada consulta.
SMTP_SERVIDOR = os.environ.get("SMTP_SERVIDOR", "smtp.gmail.com")
SMTP_PUERTO = _entero_desde_env("SMTP_PUERTO", 587)
SMTP_USUARIO = _sin_valor_de_ejemplo(os.environ.get("SMTP_USUARIO", ""))
SMTP_CLAVE = _sin_valor_de_ejemplo(os.environ.get("SMTP_CLAVE", ""))   # NUNCA en el código: solo en el .env
