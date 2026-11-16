from proveedores.decision import contar_situaciones, decidir


def procesar_consulta(datos_bcra):
    cuentas = contar_situaciones(datos_bcra)
    decision, motivo = decidir(cuentas)
    return {
        "decision": decision,
        "situacion_deudas": {f"situacion_{s}": n for s, n in cuentas.items()},
        "motivo": motivo,
    }
