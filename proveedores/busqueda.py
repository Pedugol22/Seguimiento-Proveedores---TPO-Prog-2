from apis import padron_arca
from proveedores.validaciones import formatear_cuit, limpiar_cuit, validar_cuit


def verificar_en_arca(texto):
    cuit = limpiar_cuit(texto)

    # Este control se hace ANTES de consultar a ARCA: un CUIT mal escrito nunca sale de la computadora.
    if not validar_cuit(cuit):
        return None, "El CUIT no es válido (tiene que tener 11 dígitos y el dígito verificador correcto)."

    try:
        crudo = padron_arca.consultar_cuit(cuit)
    except padron_arca.PadronError as error:
        return None, f"No se pudo consultar a ARCA en este momento ({error}). Probá de nuevo en un rato."

    if crudo is None:
        return None, f"No se ha encontrado el CUIT {formatear_cuit(cuit)} en ARCA."

    datos = padron_arca.resumir(crudo)
    if not padron_arca.esta_activo(crudo):
        return None, (f"{datos['razon_social']} ({formatear_cuit(cuit)}) figura en ARCA pero NO está activo "
                      f"(estado de la clave: {datos['estado_clave'] or 'sin dato'}).")

    datos["cuit"] = cuit  # se usa el CUIT que validamos nosotros, siempre de 11 dígitos
    return datos, None
