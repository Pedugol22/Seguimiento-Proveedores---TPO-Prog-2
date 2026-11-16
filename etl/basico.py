import os

import pandas as pd


def armar_tabla(evaluados):
    filas = []
    for evaluacion, adjudicatario in evaluados:
        filas.append({
            "cuit": evaluacion["cuit"],
            "razon_social": adjudicatario["razon_social"],
            "organismo": adjudicatario["organismo"],
            "monto": adjudicatario["monto"],
            "estado": evaluacion["estado"],
            "puntaje": evaluacion["puntaje"],
        })
    return pd.DataFrame(filas)


def limpiar(tabla):
    tabla = tabla.drop_duplicates(subset="cuit").copy()
    tabla["razon_social"] = tabla["razon_social"].fillna("SIN DATO").str.strip().str.upper()
    tabla["monto"] = pd.to_numeric(tabla["monto"], errors="coerce").fillna(0)   # sin monto = 0
    tabla["puntaje"] = tabla["puntaje"].astype(float)
    return tabla.sort_values("puntaje", ascending=False).reset_index(drop=True)


def resumir_por_estado(tabla):
    resumen = tabla.groupby("estado").agg(cantidad=("cuit", "count"), puntaje_promedio=("puntaje", "mean"))
    return resumen.round(2).reset_index()


def guardar_csv(tabla, ruta):
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    tabla.to_csv(ruta, index=False, encoding="utf-8-sig")
    return ruta
