import os
from datetime import datetime

import pandas as pd

COLUMNAS = (
    ["razon social"]
    + [f"cantidad de situacion {situacion}" for situacion in range(1, 6)]
    + ["condicion", "cuit"]
    + ["figura en boletin oficial", "expediente", "organismo", "aviso"]
)


def datos_boletin(coincidencias):
    if coincidencias is None:
        return ["No se pudo consultar", "", "", ""]
    if not coincidencias:
        return ["No", "", "", ""]
    return ["Si"] + [" | ".join(str(adj[campo]) for adj in coincidencias)
                     for campo in ("expediente", "organismo", "fuente")]


def armar_detalle(razon_social, cuit, situacion_deudas, decision, coincidencias_boletin=None):
    fila = ([razon_social] + [situacion_deudas[f"situacion_{n}"] for n in range(1, 6)] + [decision, cuit]
            + datos_boletin(coincidencias_boletin))
    return pd.DataFrame([fila], columns=COLUMNAS)


def nombre_archivo(cuit, fecha=None):
    fecha = fecha or datetime.now()
    return f"consulta_{cuit}_{fecha.strftime('%Y%m%d_%H%M%S')}.xlsx"


def guardar_excel_consulta(razon_social, cuit, situacion_deudas, decision, carpeta, fecha=None,
                           coincidencias_boletin=None):
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, nombre_archivo(cuit, fecha))
    tabla = armar_detalle(razon_social, cuit, situacion_deudas, decision, coincidencias_boletin)

    with pd.ExcelWriter(ruta, engine="openpyxl") as escritor:
        tabla.to_excel(escritor, sheet_name="Consulta", index=False)
        hoja = escritor.sheets["Consulta"]
        for numero, columna in enumerate(tabla.columns, start=1):   # ancho según el contenido (solo estética)
            ancho = max(len(str(columna)), len(str(tabla.iloc[0][columna])))
            hoja.column_dimensions[hoja.cell(row=1, column=numero).column_letter].width = min(ancho + 2, 60)
    return ruta
