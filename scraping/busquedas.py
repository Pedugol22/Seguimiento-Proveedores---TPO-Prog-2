import re

from bs4 import BeautifulSoup

PATRON_AVISO = re.compile(r"^/detalleAviso/tercera/\d+/\d{8}")


def por_etiqueta(sopa):
    return sopa.find_all("h5")


def por_clase(sopa):
    return sopa.find_all("p", class_="item")


def por_id(sopa):
    return sopa.find(id="avisosSeccionDiv")


def por_atributos(sopa):
    return sopa.find_all("a", attrs={"href": PATRON_AVISO})


def por_texto(sopa, patron="adjudicaci"):
    return sopa.find_all("h5", string=re.compile(patron, re.IGNORECASE))


def por_funcion(sopa):
    return sopa.find_all(
        lambda etiqueta: etiqueta.name == "a"
        and etiqueta.get("href", "").startswith("/detalleAviso")
        and etiqueta.find("p", class_="item") is not None
    )


def combinada(sopa, limite=2):
    return sopa.find_all("div", class_="linea-aviso", limit=limite)


def extraer_valores(etiqueta):
    return {
        "texto": etiqueta.get_text(" ", strip=True),
        "href": etiqueta.get("href"),
        "src": etiqueta.get("src"),
        "clases": etiqueta.get("class", []),
        "id": etiqueta.get("id"),
        "data": {
            nombre: valor for nombre, valor in etiqueta.attrs.items() if nombre.startswith("data-")
        },
    }


def resumen_busquedas(html):
    sopa = BeautifulSoup(html, "html.parser")
    return {
        "por etiqueta (h5)": len(por_etiqueta(sopa)),
        "por clase (p.item)": len(por_clase(sopa)),
        "por id (#avisosSeccionDiv)": 1 if por_id(sopa) is not None else 0,
        "por atributos (href con regex)": len(por_atributos(sopa)),
        "por texto (rubros 'adjudicaci')": len(por_texto(sopa)),
        "por función lambda (a + p.item)": len(por_funcion(sopa)),
        "combinada (div.linea-aviso, límite 2)": len(combinada(sopa)),
    }
