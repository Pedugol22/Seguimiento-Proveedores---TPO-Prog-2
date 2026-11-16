import time

import requests

from config.ajustes import FUENTES, PARAMETROS_HTTP

REINTENTOS = 3
PAUSA_REINTENTO = 2.0

_ultimo_pedido = 0.0


class PadronError(Exception):
    pass


class PadronNoDisponible(PadronError):
    pass


def _esperar_turno():
    global _ultimo_pedido
    if _ultimo_pedido:
        falta = PARAMETROS_HTTP["pausa_entre_pedidos"] - (time.monotonic() - _ultimo_pedido)
        if falta > 0:
            time.sleep(falta)
    _ultimo_pedido = time.monotonic()


def consultar_cuit(cuit):
    _esperar_turno()
    encabezados = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": PARAMETROS_HTTP["user_agent"],
    }

    for intento in range(1, REINTENTOS + 1):
        ultimo = intento == REINTENTOS
        try:
            respuesta = requests.post(
                FUENTES["padron_arca"], json={"cuit": cuit}, headers=encabezados,
                timeout=PARAMETROS_HTTP["timeout"],
            )
        except requests.exceptions.RequestException as error:
            if ultimo:
                raise PadronNoDisponible(f"No se pudo conectar con el servicio de ARCA: {error}") from error
            time.sleep(PAUSA_REINTENTO * intento)
            continue

        if respuesta.status_code >= 500 and not ultimo:
            time.sleep(PAUSA_REINTENTO * intento)
            continue
        break

    if respuesta.status_code == 404:
        return None
    if respuesta.status_code == 429:
        raise PadronNoDisponible("El servicio de ARCA pidió espaciar las consultas (demasiados pedidos).")
    if respuesta.status_code >= 500:
        raise PadronNoDisponible(f"El servicio de ARCA respondió con error de servidor ({respuesta.status_code}).")
    if respuesta.status_code != 200:
        raise PadronError(f"Respuesta inesperada del servicio de ARCA: HTTP {respuesta.status_code}.")

    try:
        return respuesta.json()
    except ValueError as error:
        raise PadronError("El servicio de ARCA devolvió algo que no es JSON válido.") from error


def esta_activo(datos):
    return str((datos or {}).get("estado_clave") or "").strip().upper() == "ACTIVO"


def resumir(datos):
    estructurado = datos.get("domicilio_estructurado") or {}
    return {
        "cuit": datos.get("cuit"),
        "razon_social": datos.get("nombre"),
        "tipo_persona": datos.get("tipo_persona"),
        "estado_clave": datos.get("estado_clave"),
        "condicion_iva": datos.get("condicion_iva"),
        "domicilio": datos.get("domicilio"),
        "provincia": estructurado.get("provincia"),
    }
