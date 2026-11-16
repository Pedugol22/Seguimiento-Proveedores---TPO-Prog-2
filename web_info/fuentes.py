import socket
from urllib.parse import urlparse

from config.ajustes import FUENTES


def resolver_ip(url):
    dominio = urlparse(url).hostname
    try:
        return socket.gethostbyname(dominio)
    except (socket.gaierror, TypeError):
        return None


def describir_fuentes():
    descripcion = []
    for nombre, url in FUENTES.items():
        descripcion.append({
            "nombre": nombre,
            "url": url,
            "dominio": urlparse(url).hostname,
            "ip": resolver_ip(url),
        })
    return descripcion
