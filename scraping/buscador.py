import re


def filtrar_por_rubro(avisos, palabra="adjudicaci"):
    patron = re.compile(palabra, re.IGNORECASE)
    return [a for a in avisos if patron.search(a.get("rubro", ""))]


def buscar_en_avisos(avisos, texto):
    patron = re.compile(re.escape(texto), re.IGNORECASE)
    return [
        a for a in avisos
        if patron.search(a.get("organismo", "")) or patron.search(a.get("proceso", ""))
    ]
