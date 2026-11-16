import unittest
from unittest.mock import patch

import main
from apis import cliente_api
from config import ajustes


class TestClaveDeLaApiDesdeElEnv(unittest.TestCase):
    def test_el_cliente_usa_la_clave_configurada(self):
        with patch.object(ajustes, "API_KEY_CLIENTE", "clave-del-env"):
            self.assertEqual(cliente_api._encabezados()["X-API-Key"], "clave-del-env")

    def test_sin_clave_falla_con_un_mensaje_que_manda_al_env(self):
        with patch.object(ajustes, "API_KEY_CLIENTE", ""):
            with self.assertRaises(cliente_api.ErrorApiPropia) as ctx:
                cliente_api._encabezados()
        self.assertIn(".env", str(ctx.exception))
        self.assertIn("PROVEEDORES_API_KEY", str(ctx.exception))

    def test_el_programa_no_pide_la_clave_por_terminal(self):
        self.assertFalse(hasattr(main, "_asegurar_clave"))
        self.assertFalse(hasattr(main, "getpass"))

    @patch("main._api_responde", return_value=True)
    def test_levantar_api_no_pregunta_nada(self, _):
        with patch("builtins.input", side_effect=AssertionError("no tenía que preguntar")):
            self.assertIsNone(main._levantar_api_local())


class TestValoresDeEjemploDelEnv(unittest.TestCase):
    def test_los_valores_de_ejemplo_cuentan_como_vacios(self):
        self.assertEqual(ajustes._sin_valor_de_ejemplo("tu_mail@gmail.com"), "")
        self.assertEqual(ajustes._sin_valor_de_ejemplo("pone-aca-la-contrasena-de-aplicacion"), "")
        self.assertEqual(ajustes._sin_valor_de_ejemplo("  "), "")

    def test_un_valor_real_se_conserva(self):
        self.assertEqual(ajustes._sin_valor_de_ejemplo(" alguien@gmail.com "), "alguien@gmail.com")


if __name__ == "__main__":
    unittest.main()
