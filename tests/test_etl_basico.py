import os
import tempfile
import unittest

import pandas as pd

from etl.basico import armar_tabla, guardar_csv, limpiar, resumir_por_estado


def evaluacion(cuit, estado, puntaje):
    return {"cuit": cuit, "estado": estado, "puntaje": puntaje}


def adjudicatario(nombre, monto):
    return {"razon_social": nombre, "organismo": "MINISTERIO DE PRUEBA", "monto": monto}


EVALUADOS = [
    (evaluacion("30711111111", "habilitado", 0), adjudicatario("  empresa uno s.a. ", 5000000.0)),
    (evaluacion("30722222222", "suspendido", 70), adjudicatario("Empresa Dos", None)),
    (evaluacion("30733333333", "habilitado", 3), adjudicatario("Empresa Tres", 100.0)),
    (evaluacion("30711111111", "habilitado", 0), adjudicatario("  empresa uno s.a. ", 5000000.0)),  # repetida
]


class TestEtlBasico(unittest.TestCase):
    def setUp(self):
        self.tabla = limpiar(armar_tabla(EVALUADOS))

    def test_armar_tabla(self):
        tabla = armar_tabla(EVALUADOS)
        self.assertEqual(len(tabla), 4)
        self.assertEqual(list(tabla.columns), ["cuit", "razon_social", "organismo", "monto", "estado", "puntaje"])

    def test_limpiar_saca_repetidos_y_ordena(self):
        self.assertEqual(len(self.tabla), 3)
        self.assertEqual(self.tabla.loc[0, "cuit"], "30722222222")   # el de mayor puntaje primero

    def test_limpiar_nulos_y_tipos(self):
        suspendido = self.tabla[self.tabla["estado"] == "suspendido"].iloc[0]
        self.assertEqual(suspendido["monto"], 0)                      # el monto nulo pasa a 0
        self.assertEqual(self.tabla["razon_social"].iloc[2], "EMPRESA UNO S.A.")
        self.assertTrue(pd.api.types.is_float_dtype(self.tabla["puntaje"]))

    def test_resumen_por_estado(self):
        resumen = resumir_por_estado(self.tabla).set_index("estado")
        self.assertEqual(resumen.loc["habilitado", "cantidad"], 2)
        self.assertEqual(resumen.loc["habilitado", "puntaje_promedio"], 1.5)
        self.assertEqual(resumen.loc["suspendido", "cantidad"], 1)

    def test_guardar_csv_y_releerlo(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = guardar_csv(self.tabla, os.path.join(carpeta, "salidas", "ranking.csv"))
            leido = pd.read_csv(ruta, dtype={"cuit": str})
            self.assertEqual(len(leido), 3)
            self.assertEqual(leido.loc[0, "cuit"], "30722222222")


if __name__ == "__main__":
    unittest.main()
