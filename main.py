import argparse
import sys
import threading
import time
from urllib.parse import urlparse

import requests

from apis import bcra, cliente_api
from config import ajustes
from correo import enviar as correo
from proveedores.busqueda import verificar_en_arca
from proveedores.validaciones import formatear_cuit, parece_mail
from reportes.consulta_excel import guardar_excel_consulta
from scraping.boletin_oficial import obtener_adjudicatarios
from scraping.descargar import ErrorScraping


def comando_buscar(args):
    servidor = _levantar_api_local()
    try:
        _hacer_busqueda(args)
    finally:
        if servidor is not None:
            servidor.should_exit = True


LIMITE_AVISOS_BOLETIN = 10


def _cargar_boletin():
    print("Consultando el Boletín Oficial (scraping, puede tardar unos segundos)...")
    try:
        return obtener_adjudicatarios(None, LIMITE_AVISOS_BOLETIN)
    except ErrorScraping as error:
        print(f"[i] No se pudo consultar el Boletín Oficial: {error}")
        return None


def _coincidencias_boletin(cuit, adjudicatarios):
    if adjudicatarios is None:
        return None
    return [adj for adj in adjudicatarios if adj["cuit"] == cuit]


def _mostrar_boletin(coincidencias):
    if coincidencias is None:
        return
    if not coincidencias:
        print("[Boletín Oficial] No figura entre los adjudicatarios de los avisos revisados.")
        return
    print(f"[Boletín Oficial] Figura como adjudicatario en {len(coincidencias)} aviso(s):")
    for adj in coincidencias:
        print(f"    Exp. {adj['expediente']} - {adj['organismo']}")
        print(f"    {adj['fuente']}")


def _pedir_mail_destino(pedir, anterior=""):
    if anterior:
        consulta = f"Mail de destino del Excel (Enter = {anterior}, 'no' = no enviar): "
    else:
        consulta = "Mail de destino del Excel (Enter = no enviar): "
    while True:
        respuesta = pedir(consulta).strip()
        if respuesta.lower() in ("n", "no"):
            return ""
        if not respuesta:
            return anterior
        if parece_mail(respuesta):
            return respuesta
        print("[!] Ese mail no parece válido. Probá de nuevo.")


def _hacer_busqueda(args, pedir=input):
    cuit_inicial = args.cuit
    mail_destino = ""
    boletin = None
    boletin_consultado = False
    while True:
        texto = cuit_inicial or pedir("\nCUIT a evaluar (o 'salir'): ")
        cuit_inicial = None
        if texto.strip().lower() in ("", "salir"):
            print("Hasta luego.")
            return

        datos, motivo = verificar_en_arca(texto)
        if datos is None:
            print(f"[!] {motivo}\n    Probá con otro CUIT.")
            continue
        print(f"[OK] En ARCA: {datos['razon_social']} ({formatear_cuit(datos['cuit'])}) - "
              f"clave {datos['estado_clave']} - {datos['condicion_iva']}")

        mail_destino = _pedir_mail_destino(pedir, mail_destino)

        if not boletin_consultado:
            boletin = _cargar_boletin()
            boletin_consultado = True
        coincidencias = _coincidencias_boletin(datos["cuit"], boletin)
        _mostrar_boletin(coincidencias)

        try:
            datos_bcra = bcra.consultar_deudas(datos["cuit"])
        except bcra.BcraNoEncontrado:
            datos_bcra = None
            print("[i] El BCRA no tiene deudas registradas para este CUIT.")
        except bcra.BcraError as error:
            print(f"[!] No se pudo consultar al BCRA: {error}")
            continue

        try:
            respuesta = cliente_api.registrar_consulta(datos["cuit"], datos_bcra)
        except cliente_api.ErrorApiPropia as error:
            print(f"[!] No se pudo procesar la consulta: {error}")
            continue

        # La razón social es la "denominacion" del BCRA; si el BCRA no tiene datos, la que informó ARCA.
        razon_social = (datos_bcra or {}).get("denominacion") or datos["razon_social"]
        _mostrar_resultado(razon_social, datos["cuit"], respuesta)
        _guardar_y_enviar(razon_social, datos["cuit"], respuesta, mail_destino, coincidencias)


VIABILIDAD = {
    "Aceptar": "SÍ es viable como proveedor.",
    "Revisar": "A REVISAR: no se descarta, pero hay que analizarlo antes de aceptarlo.",
    "Rechazar": "NO es viable como proveedor.",
}


def _mostrar_resultado(razon_social, cuit, respuesta):
    situaciones = respuesta["situacion_deudas"]
    print(f"\n{razon_social} ({formatear_cuit(cuit)})")
    print("Entidades por situación: " + " | ".join(
        f"{n}: {situaciones[f'situacion_{n}']}" for n in range(1, 6)))
    print(f"DECISIÓN: {respuesta['decision']} - {VIABILIDAD.get(respuesta['decision'], '')}")
    print(f"Motivo: {respuesta['motivo']}")


def _guardar_y_enviar(razon_social, cuit, respuesta, mail_destino, coincidencias=None):
    ruta = guardar_excel_consulta(razon_social, cuit, respuesta["situacion_deudas"],
                                respuesta["decision"], ajustes.CARPETA_SALIDAS,
                                coincidencias_boletin=coincidencias)
    print(f"Excel guardado en: {ruta}")
    if not mail_destino:
        print("[i] Mail no enviado: no indicaste un mail de destino.")
        return
    asunto = f"Consulta de proveedor: {razon_social} ({cuit}) - {respuesta['decision']}"
    cuerpo = (f"Adjunto el detalle de la consulta de {razon_social} (CUIT {cuit}).\n"
              f"Decisión: {respuesta['decision']}. {respuesta['motivo']}\n")
    try:
        correo.enviar(mail_destino, asunto, cuerpo, ruta)
        print(f"Mail enviado a {mail_destino}.")
    except correo.ErrorCorreo as error:
        print(f"[!] No se pudo enviar el mail: {error}")


def _api_responde():
    try:
        return requests.get(f"{ajustes.API_URL}/salud", timeout=2).status_code == 200
    except requests.RequestException:
        return False


def _levantar_api_local():
    if _api_responde():
        return None

    anfitrion = urlparse(ajustes.API_URL).hostname
    if anfitrion not in ("127.0.0.1", "localhost"):
        raise cliente_api.ErrorApiPropia(f"No hay una API respondiendo en {ajustes.API_URL}.")

    # Si no hay claves de servidor definidas, se usa la del cliente (misma clave en las dos puntas).
    if not ajustes.API_KEYS_VALIDAS and ajustes.API_KEY_CLIENTE:
        ajustes.API_KEYS_VALIDAS = [ajustes.API_KEY_CLIENTE]

    import uvicorn
    puerto = urlparse(ajustes.API_URL).port or 8000
    servidor = uvicorn.Server(uvicorn.Config(
        "api_propia.servidor:app", host="127.0.0.1", port=puerto, log_level="warning"))
    threading.Thread(target=servidor.run, daemon=True).start()

    for _ in range(50):
        if _api_responde():
            return servidor
        time.sleep(0.1)
    raise cliente_api.ErrorApiPropia("No se pudo levantar la API local.")


def construir_parser():
    parser = argparse.ArgumentParser(description="Evaluación de proveedores: pide un CUIT y decide si es apto.")
    parser.add_argument("cuit", nargs="?", help="CUIT a evaluar (si no se pone, se pide por teclado)")
    return parser


def main():
    args = construir_parser().parse_args()
    try:
        comando_buscar(args)
    except (ErrorScraping, cliente_api.ErrorApiPropia) as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
