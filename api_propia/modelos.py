from datetime import date
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from config.ajustes import ESTADOS_DOCUMENTALES
from proveedores.validaciones import limpiar_cuit, validar_cuit


def normalizar_cuit(valor):
    digitos = limpiar_cuit(valor)
    if not validar_cuit(digitos):
        raise ValueError("CUIT inválido: debe tener 11 dígitos y dígito verificador correcto.")
    return digitos


class DocumentoEntrada(BaseModel):
    nombre: str = Field(..., description="Nombre del documento (ej. constancia de inscripción).")
    estado: str = Field("vigente", description=f"Uno de: {', '.join(ESTADOS_DOCUMENTALES)}.")
    vence: Optional[date] = Field(None, description="Fecha de vencimiento (AAAA-MM-DD), si tiene.")

    @field_validator("estado")
    @classmethod
    def validar_estado(cls, valor):
        if valor not in ESTADOS_DOCUMENTALES:
            raise ValueError(f"Estado inválido. Opciones: {', '.join(ESTADOS_DOCUMENTALES)}")
        return valor


class ProveedorEntrada(BaseModel):
    cuit: str = Field(..., description="CUIT del proveedor, con o sin guiones.", examples=["30-50001091-2"])
    incidencias_internas: int = Field(0, ge=0, description="Incidencias registradas por la empresa.")
    cumplimiento_documental: float = Field(
        1.0, ge=0, le=1, description="Proporción de documentación entregada (0 a 1)."
    )
    documentos: Optional[List[DocumentoEntrada]] = Field(
        None,
        description="Documentos del proveedor. Si se envían, el cumplimiento y los vencimientos "
                    "se calculan a partir de ellos y reemplazan a cumplimiento_documental.",
    )

    @field_validator("cuit")
    @classmethod
    def validar_cuit_campo(cls, valor):
        return normalizar_cuit(valor)


class Evidencia(BaseModel):
    factor: str
    detalle: str
    puntos: float


class EvaluacionSalida(BaseModel):
    cuit: str
    denominacion: Optional[str] = None
    estado: str
    puntaje: float
    evidencias: List[Evidencia]
    encontrado_en_bcra: bool
    es_critico: bool = False
    documentos: Optional[Dict[str, Any]] = None
    datos_bcra: Dict[str, Any]
    datos_cheques: Dict[str, Any]


class ConsultaBcraSalida(BaseModel):
    cuit: str
    deudas: Dict[str, Any]
    cheques: Dict[str, Any]


class EntidadBcra(BaseModel):
    model_config = ConfigDict(extra="allow")

    entidad: Optional[str] = None
    situacion: Optional[int] = Field(None, description="Situación informada por el BCRA (1 a 5).")


class PeriodoBcra(BaseModel):
    model_config = ConfigDict(extra="allow")

    periodo: Optional[str] = Field(None, description="Período informado, AAAAMM.")
    entidades: List[EntidadBcra] = Field(default_factory=list)


class DatosBcra(BaseModel):
    model_config = ConfigDict(extra="allow")

    identificacion: Optional[Union[int, str]] = None
    denominacion: Optional[str] = None
    periodos: List[PeriodoBcra] = Field(default_factory=list)


class ConsultaEntrada(BaseModel):
    cuit: str = Field(..., description="CUIT consultado, con o sin guiones.", examples=["30-50001091-2"])
    datos_bcra: Optional[DatosBcra] = Field(
        None, description="Respuesta del BCRA para ese CUIT. Si no se manda, la API consulta al BCRA por su cuenta. null = el BCRA no tiene datos.")

    @field_validator("cuit")
    @classmethod
    def validar_cuit_campo(cls, valor):
        return normalizar_cuit(valor)


class SituacionDeudas(BaseModel):
    situacion_1: int
    situacion_2: int
    situacion_3: int
    situacion_4: int
    situacion_5: int


class ConsultaSalida(BaseModel):
    decision: str = Field(..., description="Aceptar, Revisar o Rechazar.")
    situacion_deudas: SituacionDeudas
    motivo: str
