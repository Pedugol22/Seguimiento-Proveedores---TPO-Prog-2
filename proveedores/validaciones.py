import re

# CUIT que empiezan con estos prefijos corresponden a personas jurídicas (empresas).
# Los prefijos 20, 23, 24 y 27 son personas humanas. Hoy el flujo principal (buscar) y la API
# aceptan los dos tipos; el filtro por prefijo solo lo usa el scraping del Boletín.
PREFIJOS_PERSONA_JURIDICA = ("30", "33", "34")

_PESOS_CUIT = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]


def limpiar_cuit(cuit):
    return re.sub(r"\D", "", str(cuit))


def validar_cuit(cuit):
    digitos = limpiar_cuit(cuit)
    if len(digitos) != 11:
        return False

    suma = sum(int(d) * peso for d, peso in zip(digitos[:10], _PESOS_CUIT))
    resto = suma % 11
    verificador = 0 if resto == 0 else 11 - resto
    if verificador == 10:
        return False
    return verificador == int(digitos[10])


def es_persona_juridica(cuit):
    return limpiar_cuit(cuit)[:2] in PREFIJOS_PERSONA_JURIDICA


def parece_mail(texto):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(texto).strip()))


def formatear_cuit(cuit):
    d = limpiar_cuit(cuit)
    return f"{d[:2]}-{d[2:10]}-{d[10]}" if len(d) == 11 else d


def normalizar_razon_social(nombre):
    return " ".join(str(nombre).split()).upper().rstrip(".,;:")


def limpiar_razon_social(nombre):
    return " ".join(str(nombre).split()).title()
