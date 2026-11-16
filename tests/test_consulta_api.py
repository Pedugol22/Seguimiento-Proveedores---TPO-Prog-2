import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from apis import bcra as modulo_bcra
from api_propia.servidor import app
from config import ajustes

CUIT = "30500010912"
CLAVE = "clave-de-prueba"
CABECERAS = {"X-API-Key": CLAVE}


def bcra(*situaciones, denominacion="EMPRESA DE PRUEBA S.A."):
    return {"identificacion": int(CUIT), "denominacion": denominacion, "periodos": [{
        "periodo": "202509",
        "entidades": [{"entidad": f"BANCO {n}", "situacion": s, "monto": 100.5, "diasAtrasoPago": 0}
                      for n, s in enumerate(situaciones, start=1)]}]}


class TestEndpointConsultas(unittest.TestCase):
    def setUp(self):
        self.cliente = TestClient(app)
        parche = patch.object(ajustes, "API_KEYS_VALIDAS", [CLAVE])
        parche.start()
        self.addCleanup(parche.stop)

    def _post(self, **cuerpo):
        cuerpo.setdefault("cuit", CUIT)
        return self.cliente.post("/proveedores/consultas", headers=CABECERAS, json=cuerpo)

    def test_requiere_api_key(self):
        r = self.cliente.post("/proveedores/consultas", json={"cuit": CUIT})
        self.assertEqual(r.status_code, 401)
        r = self.cliente.post("/proveedores/consultas", headers={"X-API-Key": "mala"}, json={"cuit": CUIT})
        self.assertEqual(r.status_code, 401)

    def test_la_respuesta_tiene_la_forma_del_documento(self):
        r = self._post(datos_bcra=bcra(1, 1, 4, 4, 4))
        self.assertEqual(r.status_code, 200)
        cuerpo = r.json()
        self.assertEqual(cuerpo["decision"], "Revisar")
        self.assertEqual(cuerpo["situacion_deudas"], {
            "situacion_1": 2, "situacion_2": 0, "situacion_3": 0, "situacion_4": 3, "situacion_5": 0})
        self.assertEqual(set(cuerpo), {"decision", "situacion_deudas", "motivo"})

    def test_todas_en_1_se_acepta(self):
        self.assertEqual(self._post(datos_bcra=bcra(1, 1)).json()["decision"], "Aceptar")

    def test_alguna_entre_2_y_4_se_revisa(self):
        self.assertEqual(self._post(datos_bcra=bcra(1, 3)).json()["decision"], "Revisar")

    def test_alguna_en_5_se_rechaza(self):
        self.assertEqual(self._post(datos_bcra=bcra(1, 2, 5)).json()["decision"], "Rechazar")

    def test_sin_datos_del_bcra_se_acepta(self):
        cuerpo = self._post(datos_bcra=None).json()
        self.assertEqual(cuerpo["decision"], "Aceptar")
        self.assertEqual(sum(cuerpo["situacion_deudas"].values()), 0)

    def test_solo_con_cuit_la_api_consulta_al_bcra(self):
        with patch.object(modulo_bcra, "consultar_deudas", return_value=bcra(1, 3)) as consulta:
            cuerpo = self._post().json()
        consulta.assert_called_once_with(CUIT)
        self.assertEqual(cuerpo["decision"], "Revisar")
        self.assertEqual(cuerpo["situacion_deudas"]["situacion_3"], 1)

    def test_solo_con_cuit_y_bcra_sin_datos_se_acepta(self):
        with patch.object(modulo_bcra, "consultar_deudas", side_effect=modulo_bcra.BcraNoEncontrado("x")):
            self.assertEqual(self._post().json()["decision"], "Aceptar")

    def test_solo_con_cuit_y_bcra_caido_502(self):
        with patch.object(modulo_bcra, "consultar_deudas", side_effect=modulo_bcra.BcraNoDisponible("caído")):
            self.assertEqual(self._post().status_code, 502)

    def test_con_datos_null_no_consulta_al_bcra(self):
        with patch.object(modulo_bcra, "consultar_deudas") as consulta:
            self._post(datos_bcra=None)
        consulta.assert_not_called()

    def test_cuit_invalido_422(self):
        self.assertEqual(self._post(cuit="30500010913").status_code, 422)

    def test_acepta_cuit_con_guiones(self):
        self.assertEqual(self._post(cuit="30-50001091-2", datos_bcra=bcra(1)).status_code, 200)


if __name__ == "__main__":
    unittest.main()
