import unittest

from proveedores.decision import ACEPTAR, RECHAZAR, REVISAR, contar_situaciones, decidir


def bcra(*situaciones, periodo="202509"):
    return {"periodos": [{"periodo": periodo, "entidades": [{"situacion": s} for s in situaciones]}]}


class TestContarSituaciones(unittest.TestCase):
    def test_cuenta_entidades_por_situacion(self):
        self.assertEqual(contar_situaciones(bcra(1, 1, 2, 5)), {1: 2, 2: 1, 3: 0, 4: 0, 5: 1})

    def test_sin_datos_todo_en_cero(self):
        vacio = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        self.assertEqual(contar_situaciones(None), vacio)
        self.assertEqual(contar_situaciones({}), vacio)
        self.assertEqual(contar_situaciones({"periodos": []}), vacio)

    def test_usa_solo_el_periodo_mas_reciente(self):
        datos = {"periodos": [
            {"periodo": "202508", "entidades": [{"situacion": 5}]},
            {"periodo": "202509", "entidades": [{"situacion": 1}]},
        ]}
        self.assertEqual(contar_situaciones(datos)[5], 0)
        self.assertEqual(contar_situaciones(datos)[1], 1)

    def test_situacion_mayor_a_5_cuenta_como_5(self):
        self.assertEqual(contar_situaciones(bcra(6))[5], 1)

    def test_ignora_situaciones_vacias_o_cero(self):
        datos = {"periodos": [{"periodo": "202509", "entidades": [{"situacion": None}, {}, {"situacion": 0}]}]}
        self.assertEqual(sum(contar_situaciones(datos).values()), 0)


class TestDecidir(unittest.TestCase):
    def _decidir(self, *situaciones):
        return decidir(contar_situaciones(bcra(*situaciones)))

    def test_todas_en_situacion_1_se_acepta(self):
        self.assertEqual(self._decidir(1, 1, 1)[0], ACEPTAR)

    def test_sin_deudas_se_acepta(self):
        condicion, motivo = decidir(contar_situaciones(None))
        self.assertEqual(condicion, ACEPTAR)
        self.assertIn("No tiene deudas", motivo)

    def test_alguna_entre_2_y_4_se_revisa(self):
        for situacion in (2, 3, 4):
            with self.subTest(situacion=situacion):
                self.assertEqual(self._decidir(1, situacion)[0], REVISAR)

    def test_alguna_en_5_se_rechaza(self):
        self.assertEqual(self._decidir(1, 5)[0], RECHAZAR)

    def test_la_5_gana_sobre_las_intermedias(self):
        self.assertEqual(self._decidir(2, 3, 4, 5)[0], RECHAZAR)

    def test_el_motivo_explica_la_decision(self):
        self.assertIn("situación 5", self._decidir(5)[1])
        self.assertIn("2 en situación 3", self._decidir(1, 3, 3)[1])


if __name__ == "__main__":
    unittest.main()
