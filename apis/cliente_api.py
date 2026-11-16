import requests

from config import ajustes
from config.ajustes import API_URL, PARAMETROS_HTTP


class ErrorApiPropia(Exception):
    pass


def _encabezados():
    # La clave sale del .env (PROVEEDORES_API_KEY) y nunca está escrita en el código.
    if not ajustes.API_KEY_CLIENTE:
        raise ErrorApiPropia(
            "Falta la clave de la API: definí PROVEEDORES_API_KEY en el archivo .env (ver .env.example)."
        )
    return {"X-API-Key": ajustes.API_KEY_CLIENTE, "Accept": "application/json"}


def _interpretar(respuesta):
    if respuesta.status_code == 200:
        return respuesta.json()
    try:
        detalle = respuesta.json().get("detail", respuesta.text)
    except ValueError:
        detalle = respuesta.text
    mensajes = {
        401: "No autorizado: la API key es inválida o falta.",
        404: "No se encontraron datos para ese CUIT.",
        422: "Datos inválidos",
        502: "La API propia no pudo consultar al BCRA",
        503: "La API propia no está configurada (sin API keys)",
    }
    base = mensajes.get(respuesta.status_code, f"Error HTTP {respuesta.status_code}")
    raise ErrorApiPropia(f"{base}: {detalle}")


def _llamar(metodo, ruta, **kwargs):
    try:
        respuesta = requests.request(
            metodo, f"{API_URL}{ruta}", headers=_encabezados(),
            timeout=PARAMETROS_HTTP["timeout"], **kwargs
        )
    except requests.exceptions.ConnectionError as error:
        raise ErrorApiPropia(
            f"No se pudo conectar con la API en {API_URL}. ¿Está corriendo 'python main.py servidor'?"
        ) from error
    except requests.exceptions.Timeout as error:
        raise ErrorApiPropia("La API propia no respondió a tiempo.") from error
    return _interpretar(respuesta)


def consultar_bcra(cuit):
    return _llamar("GET", f"/proveedores/{cuit}/bcra")


def registrar_consulta(cuit, datos_bcra=None):
    return _llamar("POST", "/proveedores/consultas", json={"cuit": cuit, "datos_bcra": datos_bcra})


def evaluar_proveedor(cuit, incidencias_internas=0, cumplimiento_documental=1.0):
    cuerpo = {
        "cuit": cuit,
        "incidencias_internas": incidencias_internas,
        "cumplimiento_documental": cumplimiento_documental,
    }
    return _llamar("POST", "/proveedores/evaluar", json=cuerpo)
