from fastapi import Depends, FastAPI, HTTPException

from apis import bcra
from api_propia.modelos import (
    ConsultaBcraSalida, ConsultaEntrada, ConsultaSalida, EvaluacionSalida, ProveedorEntrada,
    normalizar_cuit,
)
from api_propia.seguridad import verificar_api_key
from proveedores.consulta import procesar_consulta
from proveedores.servicio import evaluar_por_cuit

app = FastAPI(
    title="API de seguimiento de proveedores",
    description="Recibe lo que informó el BCRA para un CUIT y devuelve la decisión (Aceptar, Revisar o Rechazar). "
                "También consulta la Central de Deudores y evalúa el riesgo del proveedor.",
    version="1.0.0",
)


@app.get("/salud")
def salud():
    return {"estado": "ok"}


@app.post("/proveedores/consultas", response_model=ConsultaSalida,
          dependencies=[Depends(verificar_api_key)])
def registrar_consulta(consulta: ConsultaEntrada):
    if "datos_bcra" in consulta.model_fields_set:
        datos_bcra = consulta.datos_bcra.model_dump() if consulta.datos_bcra else None
        return procesar_consulta(datos_bcra)

    try:
        datos_bcra = bcra.consultar_deudas(consulta.cuit)
    except bcra.BcraNoEncontrado:
        datos_bcra = None
    except bcra.BcraError as error:
        raise HTTPException(status_code=502, detail=str(error))
    return procesar_consulta(datos_bcra)


@app.get("/proveedores/{cuit}/bcra", response_model=ConsultaBcraSalida,
         dependencies=[Depends(verificar_api_key)])
def consultar_bcra(cuit: str):
    try:
        cuit_limpio = normalizar_cuit(cuit)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))

    try:
        deudas = bcra.resumir_deudas(bcra.consultar_deudas(cuit_limpio))
        cheques = bcra.resumir_cheques(bcra.consultar_cheques_rechazados(cuit_limpio))
    except bcra.BcraNoEncontrado:
        raise HTTPException(status_code=404, detail="El BCRA no tiene datos para ese CUIT.")
    except bcra.BcraNoDisponible as error:
        raise HTTPException(status_code=502, detail=str(error))
    except bcra.BcraError as error:
        raise HTTPException(status_code=502, detail=str(error))

    return {"cuit": cuit_limpio, "deudas": deudas, "cheques": cheques}


@app.post("/proveedores/evaluar", response_model=EvaluacionSalida,
          dependencies=[Depends(verificar_api_key)])
def evaluar(proveedor: ProveedorEntrada):
    try:
        documentos = [doc.model_dump() for doc in proveedor.documentos] if proveedor.documentos else None
        return evaluar_por_cuit(
            proveedor.cuit, proveedor.incidencias_internas, proveedor.cumplimiento_documental,
            documentos,
        )
    except bcra.BcraNoDisponible as error:
        raise HTTPException(status_code=502, detail=str(error))
    except bcra.BcraError as error:
        raise HTTPException(status_code=502, detail=str(error))
