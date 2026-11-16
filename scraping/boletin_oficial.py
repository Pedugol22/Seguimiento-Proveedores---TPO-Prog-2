from datetime import date

from config.ajustes import FUENTES
from proveedores.textos import (
    detectar_palabras_clave, extraer_adjudicatarios, extraer_codigo_expediente, extraer_objeto,
)
from proveedores.validaciones import es_persona_juridica, validar_cuit
from scraping.buscador import filtrar_por_rubro
from scraping.descargar import descargar_html
from scraping.parsear import parsear_detalle, parsear_listado


def url_listado(fecha=None):
    base = f"{FUENTES['boletin_oficial']}/seccion/tercera"
    if fecha is None:
        return base
    if isinstance(fecha, date):
        fecha = fecha.strftime("%Y%m%d")
    return f"{base}/{fecha}"


def obtener_avisos_adjudicacion(fecha=None):
    html = descargar_html(url_listado(fecha))
    return filtrar_por_rubro(parsear_listado(html, FUENTES["boletin_oficial"]))


def listar_expedientes(adjudicatarios):
    expedientes = []
    for adjudicatario in adjudicatarios:
        expediente = adjudicatario.get("expediente")
        if expediente and expediente not in expedientes:
            expedientes.append(expediente)
    return expedientes


def obtener_adjudicatarios(fecha=None, limite_avisos=10):
    resultados = []
    for aviso in obtener_avisos_adjudicacion(fecha)[:limite_avisos]:
        detalle = parsear_detalle(descargar_html(aviso["url_detalle"]))
        texto = detalle["texto"]
        expediente = extraer_codigo_expediente(texto)
        objeto = extraer_objeto(texto)
        alertas = detectar_palabras_clave(texto)
        for adj in extraer_adjudicatarios(texto):
            if not validar_cuit(adj["cuit"]) or not es_persona_juridica(adj["cuit"]):
                continue
            resultados.append({
                **adj,
                "organismo": aviso["organismo"],
                "expediente": expediente,
                "objeto": objeto,
                "alertas": alertas,
                "fuente": aviso["url_detalle"],
            })
    return resultados
