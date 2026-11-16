import io
import os
import smtplib
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import requests

import main
from apis import bcra, cliente_api, padron_arca
from config import ajustes
from correo import enviar as correo
from proveedores.busqueda import verificar_en_arca
from reportes import consulta_excel
from scraping.descargar import ErrorScraping

CUIT_ACTIVO = "30500010912"      # CUIT válido (módulo 11) de una sociedad
CUIT_INVALIDO = "30500010913"
CUIT_PERSONA = "20711111116"

ARCA_ACTIVO = {
    "cuit": CUIT_ACTIVO, "nombre": "EMPRESA DE PRUEBA S.A.", "tipo_persona": "JURIDICA",
    "estado_clave": "ACTIVO", "condicion_iva": "Responsable Inscripto",
    "domicilio": "CALLE FALSA 123, CIUDAD AUTONOMA BUENOS AIRES",
    "domicilio_estructurado": {"direccion": "CALLE FALSA 123", "localidad": None,
                               "provincia": "CIUDAD AUTONOMA BUENOS AIRES", "cod_postal": "1036"},
    "monotributo_categoria": None,
}

EVALUACION = {
    "cuit": CUIT_ACTIVO, "denominacion": "EMPRESA DE PRUEBA S.A.", "estado": "observado", "puntaje": 17.0,
    "evidencias": [{"factor": "situacion", "detalle": "Situación 2 en el BCRA", "puntos": 12.0},
                   {"factor": "dias_atraso", "detalle": "50 días de atraso", "puntos": 5.0}],
    "encontrado_en_bcra": True, "es_critico": False,
    "datos_bcra": {"situacion_maxima": 2, "monto_total_miles": 150.5, "dias_atraso_max": 50},
    "datos_cheques": {"cheques_rechazados": 1, "multas_impagas": 0},
}


def respuesta(codigo, cuerpo=None):
    r = MagicMock()
    r.status_code = codigo
    r.json.return_value = cuerpo if cuerpo is not None else {}
    return r


class SinPausas(unittest.TestCase):

    def setUp(self):
        for objetivo in ("apis.padron_arca.time.sleep",):
            parche = patch(objetivo)
            parche.start()
            self.addCleanup(parche.stop)
        padron_arca._ultimo_pedido = 0.0


class TestPadronArca(SinPausas):
    @patch("apis.padron_arca.requests.post")
    def test_cuit_activo_devuelve_datos(self, post):
        post.return_value = respuesta(200, ARCA_ACTIVO)
        datos = padron_arca.consultar_cuit(CUIT_ACTIVO)
        self.assertEqual(datos["nombre"], "EMPRESA DE PRUEBA S.A.")
        _, kwargs = post.call_args
        self.assertEqual(kwargs["json"], {"cuit": CUIT_ACTIVO})
        self.assertIn("TP-UADE", kwargs["headers"]["User-Agent"])

    @patch("apis.padron_arca.requests.post")
    def test_404_devuelve_none(self, post):
        post.return_value = respuesta(404, {"detail": "padron_sin_datos"})
        self.assertIsNone(padron_arca.consultar_cuit(CUIT_ACTIVO))

    @patch("apis.padron_arca.requests.post", side_effect=requests.exceptions.ConnectionError("corte"))
    def test_sin_conexion_reintenta_y_falla(self, post):
        with self.assertRaises(padron_arca.PadronNoDisponible):
            padron_arca.consultar_cuit(CUIT_ACTIVO)
        self.assertEqual(post.call_count, padron_arca.REINTENTOS)

    @patch("apis.padron_arca.requests.post")
    def test_error_500_reintenta(self, post):
        post.side_effect = [respuesta(500), respuesta(200, ARCA_ACTIVO)]
        self.assertEqual(padron_arca.consultar_cuit(CUIT_ACTIVO)["estado_clave"], "ACTIVO")
        self.assertEqual(post.call_count, 2)

    @patch("apis.padron_arca.requests.post")
    def test_429_es_no_disponible(self, post):
        post.return_value = respuesta(429)
        with self.assertRaises(padron_arca.PadronNoDisponible):
            padron_arca.consultar_cuit(CUIT_ACTIVO)

    def test_activo_y_sociedad(self):
        self.assertTrue(padron_arca.esta_activo(ARCA_ACTIVO))
        self.assertTrue(padron_arca.esta_activo({"estado_clave": " activo "}))
        self.assertFalse(padron_arca.esta_activo({"estado_clave": "INACTIVO"}))
        self.assertFalse(padron_arca.esta_activo({}))

    def test_resumir(self):
        r = padron_arca.resumir(ARCA_ACTIVO)
        self.assertEqual(r["razon_social"], "EMPRESA DE PRUEBA S.A.")
        self.assertEqual(r["provincia"], "CIUDAD AUTONOMA BUENOS AIRES")


class TestVerificarEnArca(SinPausas):
    @patch("proveedores.busqueda.padron_arca.consultar_cuit")
    def test_cuit_invalido_no_consulta_a_arca(self, consultar):
        datos, motivo = verificar_en_arca(CUIT_INVALIDO)
        self.assertIsNone(datos)
        self.assertIn("no es válido", motivo)
        consultar.assert_not_called()

    @patch("proveedores.busqueda.padron_arca.consultar_cuit")
    def test_persona_humana_activa_sigue_el_flujo(self, consultar):
        consultar.return_value = dict(ARCA_ACTIVO, cuit=CUIT_PERSONA, nombre="PEREZ JUAN", tipo_persona="FISICA")
        datos, motivo = verificar_en_arca(CUIT_PERSONA)
        self.assertIsNone(motivo)
        self.assertEqual(datos["cuit"], CUIT_PERSONA)
        self.assertEqual(datos["tipo_persona"], "FISICA")

    @patch("proveedores.busqueda.padron_arca.consultar_cuit", return_value=None)
    def test_persona_humana_no_encontrada(self, _):
        datos, motivo = verificar_en_arca(CUIT_PERSONA)
        self.assertIsNone(datos)
        self.assertIn("No se ha encontrado", motivo)

    @patch("proveedores.busqueda.padron_arca.consultar_cuit", return_value=None)
    def test_no_encontrado(self, _):
        datos, motivo = verificar_en_arca("30-50001091-2")
        self.assertIsNone(datos)
        self.assertIn("No se ha encontrado", motivo)

    @patch("proveedores.busqueda.padron_arca.consultar_cuit")
    def test_no_activo(self, consultar):
        consultar.return_value = dict(ARCA_ACTIVO, estado_clave="INACTIVO")
        datos, motivo = verificar_en_arca(CUIT_ACTIVO)
        self.assertIsNone(datos)
        self.assertIn("NO está activo", motivo)

    @patch("proveedores.busqueda.padron_arca.consultar_cuit",
           side_effect=padron_arca.PadronNoDisponible("caído"))
    def test_arca_caido_no_rompe(self, _):
        datos, motivo = verificar_en_arca(CUIT_ACTIVO)
        self.assertIsNone(datos)
        self.assertIn("No se pudo consultar a ARCA", motivo)

    @patch("proveedores.busqueda.padron_arca.consultar_cuit", return_value=ARCA_ACTIVO)
    def test_activo_devuelve_datos_con_cuit_limpio(self, _):
        datos, motivo = verificar_en_arca("30-50001091-2")
        self.assertIsNone(motivo)
        self.assertEqual(datos["cuit"], CUIT_ACTIVO)
        self.assertEqual(datos["razon_social"], "EMPRESA DE PRUEBA S.A.")


class TestExcel(unittest.TestCase):
    SITUACIONES = {"situacion_1": 2, "situacion_2": 0, "situacion_3": 0, "situacion_4": 1, "situacion_5": 0}

    def test_guarda_una_fila_con_las_columnas_del_detalle(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = consulta_excel.guardar_excel_consulta(
                "EMPRESA DE PRUEBA S.A.", CUIT_ACTIVO, self.SITUACIONES, "Revisar",
                os.path.join(carpeta, "salidas"), fecha=datetime(2026, 11, 6, 20, 30, 15))
            self.assertTrue(ruta.endswith("consulta_30500010912_20261106_203015.xlsx"))
            tabla = pd.read_excel(ruta, sheet_name="Consulta", dtype={"cuit": str})
        self.assertEqual(list(tabla.columns), consulta_excel.COLUMNAS)
        self.assertEqual(tabla.columns[0], "razon social")
        self.assertEqual(tabla.columns[5], "cantidad de situacion 5")
        self.assertEqual(len(tabla), 1)
        fila = tabla.iloc[0]
        self.assertEqual(fila["razon social"], "EMPRESA DE PRUEBA S.A.")
        self.assertEqual(fila["cantidad de situacion 1"], 2)
        self.assertEqual(fila["cantidad de situacion 4"], 1)
        self.assertEqual(fila["condicion"], "Revisar")
        self.assertEqual(fila["cuit"], CUIT_ACTIVO)


class TestExcelBoletin(unittest.TestCase):
    SITUACIONES = {"situacion_1": 1, "situacion_2": 0, "situacion_3": 0, "situacion_4": 0, "situacion_5": 0}
    AVISO = {"expediente": "EX-2026-1", "organismo": "MINISTERIO DE PRUEBA", "fuente": "https://boletin/1"}

    def _leer(self, coincidencias):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = consulta_excel.guardar_excel_consulta(
                "EMPRESA", CUIT_ACTIVO, self.SITUACIONES, "Aceptar", carpeta, coincidencias_boletin=coincidencias)
            return pd.read_excel(ruta, sheet_name="Consulta", dtype=str).fillna("").iloc[0]

    def test_figura_en_el_boletin(self):
        fila = self._leer([self.AVISO, dict(self.AVISO, expediente="EX-2026-2")])
        self.assertEqual(fila["figura en boletin oficial"], "Si")
        self.assertEqual(fila["expediente"], "EX-2026-1 | EX-2026-2")
        self.assertEqual(fila["organismo"], "MINISTERIO DE PRUEBA | MINISTERIO DE PRUEBA")
        self.assertEqual(fila["aviso"], "https://boletin/1 | https://boletin/1")

    def test_no_figura(self):
        fila = self._leer([])
        self.assertEqual(fila["figura en boletin oficial"], "No")
        self.assertEqual(fila["expediente"], "")

    def test_no_se_pudo_consultar(self):
        self.assertEqual(self._leer(None)["figura en boletin oficial"], "No se pudo consultar")


class TestCorreo(unittest.TestCase):
    def setUp(self):
        for nombre, valor in (("SMTP_USUARIO", "envia@ejemplo.com"), ("SMTP_CLAVE", "clave-de-app")):
            parche = patch.object(ajustes, nombre, valor)
            parche.start()
            self.addCleanup(parche.stop)

    def _adjunto(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        ruta = os.path.join(carpeta.name, "reporte.xlsx")
        with open(ruta, "wb") as f:
            f.write(b"contenido")
        return ruta

    def test_arma_mensaje_con_adjunto(self):
        ruta = self._adjunto()
        mensaje = correo.armar_mensaje("a@x.com", "b@x.com", "Asunto", "Cuerpo", ruta)
        adjuntos = list(mensaje.iter_attachments())
        self.assertEqual(len(adjuntos), 1)
        self.assertEqual(adjuntos[0].get_filename(), "reporte.xlsx")
        self.assertEqual(mensaje["To"], "b@x.com")

    @patch("correo.enviar.smtplib.SMTP")
    def test_enviar_usa_starttls_login_y_envia_al_destinatario_indicado(self, smtp):
        servidor = smtp.return_value.__enter__.return_value
        destino = correo.enviar("destino@ejemplo.com", "Asunto", "Cuerpo", self._adjunto())
        self.assertEqual(destino, "destino@ejemplo.com")
        smtp.assert_called_once_with("smtp.gmail.com", 587, timeout=30)
        servidor.starttls.assert_called_once()
        servidor.login.assert_called_once_with("envia@ejemplo.com", "clave-de-app")
        enviado = servidor.send_message.call_args[0][0]
        self.assertEqual(enviado["To"], "destino@ejemplo.com")
        self.assertEqual(enviado["From"], "envia@ejemplo.com")

    def test_sin_credenciales_falla_con_mensaje_claro(self):
        with patch.object(ajustes, "SMTP_CLAVE", ""):
            with self.assertRaises(correo.ErrorCorreo) as ctx:
                correo.enviar("destino@ejemplo.com", "A", "B")
        self.assertIn("SMTP_CLAVE", str(ctx.exception))

    def test_sin_destinatario_falla(self):
        with self.assertRaises(correo.ErrorCorreo):
            correo.enviar("", "A", "B")

    @patch("correo.enviar.smtplib.SMTP")
    def test_clave_rechazada(self, smtp):
        smtp.return_value.__enter__.return_value.login.side_effect = smtplib.SMTPAuthenticationError(535, b"mal")
        with self.assertRaises(correo.ErrorCorreo) as ctx:
            correo.enviar("destino@ejemplo.com", "A", "B")
        self.assertIn("contraseña de aplicación", str(ctx.exception))

    @patch("correo.enviar.smtplib.SMTP", side_effect=OSError("sin red"))
    def test_sin_red(self, _):
        with self.assertRaises(correo.ErrorCorreo):
            correo.enviar("destino@ejemplo.com", "A", "B")


BCRA_OK = {"identificacion": 30500010912, "denominacion": "EMPRESA DE PRUEBA S.A.",
           "periodos": [{"periodo": "202509", "entidades": [{"situacion": 1, "monto": 20}]}]}

RESULTADO = {
    "decision": "Aceptar", "motivo": "Todas las deudas están en situación 1.",
    "situacion_deudas": {"situacion_1": 1, "situacion_2": 0, "situacion_3": 0, "situacion_4": 0, "situacion_5": 0},
}


class TestFlujoBuscar(SinPausas):

    def setUp(self):
        super().setUp()
        self.carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(self.carpeta.cleanup)
        parche = patch.object(ajustes, "CARPETA_SALIDAS", self.carpeta.name)
        parche.start()
        self.addCleanup(parche.stop)

    def _correr(self, respuestas_usuario, arca=(ARCA_ACTIVO,), bcra_respuesta=BCRA_OK, api=RESULTADO,
                argumento=None, error_mail=None, boletin=()):
        entradas = iter(respuestas_usuario)
        salida = io.StringIO()
        arca_mock = patch("proveedores.busqueda.padron_arca.consultar_cuit", side_effect=list(arca))
        bcra_mock = patch("main.bcra.consultar_deudas", **(
            {"side_effect": bcra_respuesta} if isinstance(bcra_respuesta, Exception)
            else {"return_value": bcra_respuesta}))
        api_mock = patch("main.cliente_api.registrar_consulta", **(
            {"side_effect": api} if isinstance(api, Exception) else {"return_value": api}))
        mail_mock = patch("main.correo.enviar", side_effect=error_mail, return_value="x")
        boletin_mock = patch("main.obtener_adjudicatarios", **(
            {"side_effect": boletin} if isinstance(boletin, Exception) else {"return_value": boletin}))
        with arca_mock as consultar_arca, bcra_mock as consultar_bcra, api_mock as registrar, \
                mail_mock as enviar_mail, boletin_mock as self.obtener_boletin, redirect_stdout(salida):
            main._hacer_busqueda(SimpleNamespace(cuit=argumento), pedir=lambda _m: next(entradas))
        self.enviar_mail = enviar_mail
        return salida.getvalue(), consultar_arca, consultar_bcra, registrar

    def test_flujo_completo(self):
        texto, _, consultar_bcra, registrar = self._correr([CUIT_ACTIVO, "destino@ejemplo.com", "salir"])
        consultar_bcra.assert_called_once_with(CUIT_ACTIVO)
        registrar.assert_called_once_with(CUIT_ACTIVO, BCRA_OK)
        self.assertIn("DECISIÓN: Aceptar", texto)
        self.assertIn("SÍ es viable", texto)
        self.assertIn("Excel guardado en:", texto)
        self.assertIn("Mail enviado a destino@ejemplo.com", texto)
        destino, asunto, _cuerpo, adjunto = self.enviar_mail.call_args[0]
        self.assertEqual(destino, "destino@ejemplo.com")
        self.assertIn("Aceptar", asunto)
        self.assertTrue(adjunto.endswith(".xlsx") and os.path.exists(adjunto))

    def test_no_encontrado_avisa_y_pide_otro_cuit_sin_seguir(self):
        texto, _, consultar_bcra, registrar = self._correr([CUIT_ACTIVO, "salir"], arca=[None])
        self.assertIn("No se ha encontrado", texto)
        self.assertIn("Probá con otro CUIT", texto)
        consultar_bcra.assert_not_called()
        registrar.assert_not_called()

    def test_no_activo_no_sigue(self):
        texto, _, consultar_bcra, registrar = self._correr(
            [CUIT_ACTIVO, "salir"], arca=[dict(ARCA_ACTIVO, estado_clave="INACTIVO")])
        self.assertIn("NO está activo", texto)
        consultar_bcra.assert_not_called()
        registrar.assert_not_called()

    def test_cuit_invalido_no_llega_a_arca_y_pide_otro(self):
        texto, consultar_arca, _, registrar = self._correr([CUIT_INVALIDO, CUIT_ACTIVO, "", "salir"])
        self.assertIn("no es válido", texto)
        self.assertEqual(consultar_arca.call_count, 1)
        registrar.assert_called_once()

    def test_enter_sin_mail_previo_no_envia(self):
        _, _, _, registrar = self._correr([CUIT_ACTIVO, "", "salir"])
        self.enviar_mail.assert_not_called()

    def test_no_cancela_el_envio(self):
        _, _, _, registrar = self._correr([CUIT_ACTIVO, "no", "salir"])
        self.enviar_mail.assert_not_called()

    def test_mail_mal_escrito_se_vuelve_a_pedir(self):
        texto, _, _, registrar = self._correr([CUIT_ACTIVO, "esto-no-es-un-mail", "yo@ejemplo.com", "salir"])
        self.assertIn("no parece válido", texto)
        self.assertEqual(self.enviar_mail.call_args[0][0], "yo@ejemplo.com")

    def test_el_mail_se_recuerda_para_la_siguiente_consulta(self):
        _, _, _, registrar = self._correr(
            [CUIT_ACTIVO, "yo@ejemplo.com", CUIT_ACTIVO, "", "salir"], arca=[ARCA_ACTIVO, ARCA_ACTIVO])
        self.assertEqual(registrar.call_count, 2)
        self.assertEqual(self.enviar_mail.call_count, 2)
        self.assertEqual(self.enviar_mail.call_args[0][0], "yo@ejemplo.com")

    def test_bcra_sin_datos_se_manda_igual_a_la_api(self):
        texto, _, _, registrar = self._correr(
            [CUIT_ACTIVO, "", "salir"], bcra_respuesta=bcra.BcraNoEncontrado("sin datos"))
        self.assertIn("no tiene deudas registradas", texto)
        self.assertIsNone(registrar.call_args[0][1])

    def test_bcra_caido_no_llama_a_la_api(self):
        texto, _, _, registrar = self._correr(
            [CUIT_ACTIVO, "", "salir"], bcra_respuesta=bcra.BcraNoDisponible("corte"))
        self.assertIn("No se pudo consultar al BCRA", texto)
        registrar.assert_not_called()

    def test_error_de_la_api_propia_no_corta_el_programa(self):
        texto, _, _, _ = self._correr([CUIT_ACTIVO, "", "salir"], api=cliente_api.ErrorApiPropia("401"))
        self.assertIn("No se pudo procesar la consulta", texto)
        self.assertIn("Hasta luego", texto)

    def test_mail_no_enviado_se_informa_con_el_motivo(self):
        error = correo.ErrorCorreo("Faltan SMTP_USUARIO y SMTP_CLAVE en el .env")
        texto, _, _, _ = self._correr([CUIT_ACTIVO, "x@y.com", "salir"], error_mail=error)
        self.assertIn("No se pudo enviar el mail: Faltan SMTP_USUARIO", texto)
        self.assertIn("Excel guardado en:", texto)

    def test_sin_mail_de_destino_guarda_el_excel_y_avisa(self):
        texto, _, _, _ = self._correr([CUIT_ACTIVO, "", "salir"])
        self.assertIn("Excel guardado en:", texto)
        self.assertIn("no indicaste un mail de destino", texto)

    def test_muestra_las_cantidades_y_si_es_viable(self):
        situaciones = {"situacion_1": 2, "situacion_2": 0, "situacion_3": 1, "situacion_4": 0, "situacion_5": 0}
        for decision, esperado in (("Revisar", "A REVISAR"), ("Rechazar", "NO es viable")):
            resultado = dict(RESULTADO, decision=decision, situacion_deudas=situaciones)
            texto, _, _, _ = self._correr([CUIT_ACTIVO, "", "salir"], api=resultado)
            self.assertIn("1: 2 | 2: 0 | 3: 1 | 4: 0 | 5: 0", texto)
            self.assertIn(f"DECISIÓN: {decision}", texto)
            self.assertIn(esperado, texto)

    def test_persona_humana_activa_sigue_el_flujo(self):
        humana = dict(ARCA_ACTIVO, cuit=CUIT_PERSONA, nombre="PEREZ JUAN", tipo_persona="FISICA")
        _, _, consultar_bcra, registrar = self._correr([CUIT_PERSONA, "", "salir"], arca=[humana])
        consultar_bcra.assert_called_once_with(CUIT_PERSONA)
        registrar.assert_called_once()

    def test_cuit_por_argumento_se_usa_primero(self):
        _, _, consultar_bcra, _ = self._correr(["", "salir"], argumento=CUIT_ACTIVO)
        consultar_bcra.assert_called_once_with(CUIT_ACTIVO)


    ADJUDICACION = {"cuit": CUIT_ACTIVO, "razon_social": "EMPRESA", "organismo": "MINISTERIO DE PRUEBA",
                    "expediente": "EX-2026-1", "fuente": "https://www.boletinoficial.gob.ar/detalleAviso/tercera/1/20261110"}

    def test_si_figura_en_el_boletin_lo_muestra(self):
        texto, _, _, _ = self._correr([CUIT_ACTIVO, "", "salir"], boletin=[self.ADJUDICACION])
        self.assertIn("[Boletín Oficial] Figura como adjudicatario en 1 aviso(s)", texto)
        self.assertIn("EX-2026-1 - MINISTERIO DE PRUEBA", texto)

    def test_lo_del_boletin_queda_en_el_excel_adjunto(self):
        self._correr([CUIT_ACTIVO, "destino@ejemplo.com", "salir"], boletin=[self.ADJUDICACION])
        adjunto = self.enviar_mail.call_args[0][3]
        fila = pd.read_excel(adjunto, sheet_name="Consulta", dtype=str).fillna("").iloc[0]
        self.assertEqual(fila["figura en boletin oficial"], "Si")
        self.assertEqual(fila["expediente"], "EX-2026-1")

    def test_si_no_figura_lo_avisa(self):
        otra = dict(self.ADJUDICACION, cuit="30711111111")
        texto, _, _, _ = self._correr([CUIT_ACTIVO, "", "salir"], boletin=[otra])
        self.assertIn("No figura entre los adjudicatarios", texto)

    def test_si_el_boletin_falla_el_flujo_sigue(self):
        texto, _, _, _ = self._correr([CUIT_ACTIVO, "", "salir"], boletin=ErrorScraping("sin conexión"))
        self.assertIn("No se pudo consultar el Boletín Oficial: sin conexión", texto)
        self.assertIn("DECISIÓN: Aceptar", texto)

    def test_el_boletin_se_scrapea_una_sola_vez(self):
        self._correr([CUIT_ACTIVO, "", CUIT_ACTIVO, "", "salir"], arca=(ARCA_ACTIVO, ARCA_ACTIVO))
        self.assertEqual(self.obtener_boletin.call_count, 1)

    def test_con_el_cuit_invalido_no_se_scrapea(self):
        self._correr(["123", "salir"])
        self.obtener_boletin.assert_not_called()


if __name__ == "__main__":
    unittest.main()
