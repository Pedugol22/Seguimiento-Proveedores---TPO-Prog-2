import re

from bs4 import BeautifulSoup

_PATRON_DETALLE = re.compile(r"/detalleAviso/tercera/(\d+)/(\d{8})")


def _texto(etiqueta):
    return etiqueta.get_text(" ", strip=True) if etiqueta else ""


def parsear_listado(html, url_base="https://www.boletinoficial.gob.ar"):
    sopa = BeautifulSoup(html, "html.parser")
    contenedor = sopa.find("div", id="avisosSeccionDiv")
    if contenedor is None:
        return []

    avisos = []
    rubro_actual = ""
    for elemento in contenedor.find_all(["h5", "a"]):
        if elemento.name == "h5" and "seccion-rubro" in (elemento.get("class") or []):
            rubro_actual = _texto(elemento)
            continue
        if elemento.name != "a":
            continue
        coincidencia = _PATRON_DETALLE.search(elemento.get("href", ""))
        if not coincidencia:
            continue
        linea = elemento.find("div", class_="linea-aviso")
        organismo = _texto(linea.find("p", class_="item")) if linea else ""
        detalle = linea.find("p", class_="item-detalle") if linea else None
        avisos.append({
            "rubro": rubro_actual,
            "organismo": organismo,
            "proceso": _texto(detalle.find("small")) if detalle else "",
            "id_aviso": coincidencia.group(1),
            "url_detalle": url_base + coincidencia.group(0),
        })
    return avisos


def parsear_detalle(html):
    sopa = BeautifulSoup(html, "html.parser")
    titulo = _texto(sopa.find(id="tituloDetalleAviso"))
    cuerpo = sopa.find(id="cuerpoDetalleAviso")
    parrafos = [_texto(p) for p in cuerpo.find_all("p")] if cuerpo else []
    texto = " ".join(p for p in parrafos if p) or _texto(cuerpo)
    return {"titulo": titulo, "texto": texto}
