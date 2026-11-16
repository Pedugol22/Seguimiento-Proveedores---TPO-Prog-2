SITUACIONES = (1, 2, 3, 4, 5)

ACEPTAR = "Aceptar"
REVISAR = "Revisar"
RECHAZAR = "Rechazar"


def contar_situaciones(datos_bcra):
    cuentas = {situacion: 0 for situacion in SITUACIONES}
    periodos = (datos_bcra or {}).get("periodos") or []
    if not periodos:
        return cuentas

    periodo = max(periodos, key=lambda p: p.get("periodo") or "")
    for entidad in periodo.get("entidades") or []:
        situacion = entidad.get("situacion")
        if not situacion or situacion < 1:
            continue
        cuentas[min(int(situacion), 5)] += 1   # cualquier valor mayor a 5 se cuenta como 5
    return cuentas


def decidir(cuentas):
    if cuentas[5] > 0:
        return RECHAZAR, "Tiene al menos una deuda en situación 5."

    intermedias = {s: cuentas[s] for s in (2, 3, 4) if cuentas[s] > 0}
    if intermedias:
        detalle = ", ".join(f"{cantidad} en situación {s}" for s, cantidad in intermedias.items())
        return REVISAR, f"Tiene deudas en situación 2, 3 o 4 ({detalle})."

    if sum(cuentas.values()) == 0:
        return ACEPTAR, "No tiene deudas informadas en el BCRA."
    return ACEPTAR, "Todas las deudas están en situación 1."
