# Plataforma de evaluación y seguimiento de proveedores

Trabajo práctico – Programación 2 (UADE) – Solicitud de proyecto 3.

El usuario escribe el CUIT de una empresa y el programa decide si es apta como proveedor, con datos reales:

```
CUIT ──▶ ¿activo en ARCA? ──no──▶ "no se ha encontrado / no está activo" y pide otro CUIT
              │ sí
              ▼
        Boletín Oficial (SCRAPING con requests + BeautifulSoup): ¿figura como adjudicatario?  ← informativo
              │
              ▼
        API del BCRA (Central de Deudores)          ← la consulta main.py, directo
              │
              ▼
        NUESTRA API (X-API-Key)  POST /proveedores/consultas
              │   recibe: CUIT y datos del BCRA
              ├─ cuenta cuántas entidades hay en cada situación (1 a 5)
              └─ decide:  todas en 1 → Aceptar · alguna en 2, 3 o 4 → Revisar · alguna en 5 → Rechazar
              │   responde: {"decision": "...", "situacion_deudas": {"situacion_1": n, ... "situacion_5": n}}
              ▼
        main.py: muestra en consola si es viable, guarda un Excel (Pandas) y lo envía por mail
```

El **scraping** del Boletín Oficial está dentro del flujo (paso 4).

La verificación en ARCA usa el servicio de la herramienta pública *Consulta de CUIT* de
[FactuARCA](https://factuarca.app/herramientas/consulta-cuit), que devuelve los datos de la constancia de inscripción.

## Inicio rápido

Con Python 3.10 o superior, desde la carpeta del proyecto:

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows   (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env        # Linux/Mac: cp .env.example .env
python main.py
```

El programa pide el CUIT y sigue todo el circuito. El `.env` ya viene con la clave de la API cargada (una clave de
demostración para correr todo en la propia computadora): el programa la lee de ahí y nunca la pide por la terminal.

Para que el programa **envíe el mail** hay que completar dos variables del `.env`, que vienen vacías:

```
SMTP_USUARIO=        # el Gmail desde el que salen los mails
SMTP_CLAVE=          # contraseña de aplicación de Google (no la clave normal)
```

Si quedan vacías, el programa funciona igual (decide y guarda el Excel) y avisa que no pudo enviar el mail.
El **mail de destino** no va en el `.env`: se escribe en la terminal en cada consulta.
El archivo `.env` está en `.gitignore`: **nunca se sube a GitHub**.

## Cómo funciona `python main.py`

1. Pide un CUIT por teclado (o lo toma del comando: `python main.py 30500010912`) y lo valida: 11 dígitos y
   dígito verificador. Un CUIT mal escrito se rechaza **antes** de consultar nada afuera. Se aceptan empresas y personas humanas.
2. Lo busca en ARCA. Si no figura o figura pero no está activo, muestra un cartel
   (*"No se ha encontrado..."* / *"...NO está activo..."*) y pide otro CUIT.
3. Pide el **mail de destino** del Excel (Enter = no enviar; si ya se usó uno, Enter lo repite).
4. **Scraping del Boletín Oficial**: la primera vez baja y lee con BeautifulSoup los avisos de adjudicación de la
   edición vigente (tarda unos segundos, por las pausas de cortesía) y los guarda en memoria; con los CUIT siguientes no
   vuelve a descargar. Informa si el CUIT figura como adjudicatario (expediente, organismo y link al aviso). Es
   **informativo**: no cambia la decisión, queda registrado en el Excel, y si el Boletín no responde, el flujo sigue igual.
5. Consulta al BCRA (Central de Deudores). Si el BCRA no tiene deudas registradas para ese CUIT, sigue igual.
6. Manda a **nuestra API** (`POST /proveedores/consultas`) el CUIT y lo que respondió el BCRA. La API decide
   (ver reglas abajo) y devuelve la decisión y la cantidad de deudas en cada situación.
7. Muestra en la consola las cantidades por situación y **si es viable o no**, guarda el Excel en `salidas/` y lo envía por mail.
   Vuelve a pedir otro CUIT hasta que se escriba `salir`.

El programa levanta la API propia solo, en segundo plano: no hay que arrancar nada más.

### Reglas de decisión (en nuestra API)

El BCRA informa, por cada entidad financiera, una situación del 1 al 5. Se cuentan las entidades en cada situación
(del período más reciente) y se decide en este orden:

| Si... | Decisión |
|---|---|
| alguna deuda está en situación **5** | **Rechazar** (no es viable como proveedor) |
| alguna deuda está en situación **2, 3 o 4** | **Revisar** (hay que analizarlo antes de aceptarlo) |
| todas están en situación **1** | **Aceptar** (es viable) |

Si el BCRA no tiene deudas registradas para el CUIT, no hay nada en situación 2 a 5 y la decisión es Aceptar
(el motivo lo aclara: *"No tiene deudas informadas en el BCRA"*). Está en `proveedores/decision.py`.

### El Excel

Un archivo `.xlsx` con una hoja (*Consulta*) y una fila: `razon social`, `cantidad de situacion 1` a `cantidad de situacion 5`,
`condicion` y `cuit`, y lo que salió del scraping del Boletín: `figura en boletin oficial` (*Si* / *No* / *No se pudo consultar*),
`expediente`, `organismo` y `aviso` (link). Si figura en más de un aviso, los valores van separados por ` | `.
La razón social es la *denominación* del BCRA (si el BCRA no tiene datos, la que informó ARCA).
Se guarda en `salidas/` y es el archivo que se adjunta al mail.

### El mail

Lo envía `main.py` con `smtplib` desde la cuenta del `.env` (`SMTP_USUARIO` / `SMTP_CLAVE`) al mail que escribió el usuario,
con el Excel adjunto. Si falta la cuenta o el servidor rechaza la clave, la consulta **no se pierde**: se muestra la decisión,
el Excel queda guardado y la consola explica por qué no se envió.

## La API

### Usar la API sola (Bruno, Postman, curl)

El programa levanta la API por su cuenta mientras corre. Para probarla aparte, en una terminal con el `.venv` activo:

```bash
python -m uvicorn api_propia.servidor:app --port 8000
```

La clave está en el `.env`: `API_KEYS` es la que **acepta** la API (se pueden poner varias separadas por coma) y
`PROVEEDORES_API_KEY` es la que **usa** el programa para llamarla. En una herramienta como Bruno se manda en el header
**`X-API-Key`** (valor de demostración: `clave-tp-programacion2`):

- `POST http://127.0.0.1:8000/proveedores/consultas`, header `X-API-Key`.
  - **Solo con el CUIT** (`{"cuit": "30500010912"}`): la API consulta sola al BCRA y devuelve la decisión (necesita internet).
  - **Con `datos_bcra`** (ver ejemplo abajo): usa esos datos y no consulta al BCRA. Así lo llama `main.py`.
  - Con `"datos_bcra": null` se interpreta que el BCRA no tiene datos para ese CUIT.
- Sin el header responde `401 Falta el header X-API-Key.`; con una clave equivocada, `401 API key inválida.`
- `GET http://127.0.0.1:8000/salud` es público (no pide clave).

Documentación interactiva (Swagger), con la API levantada: <http://127.0.0.1:8000/docs> (botón *Authorize* → ingresar la clave).

| Endpoint | Método | Auth | Respuestas |
|---|---|---|---|
| `/salud` | GET | no | 200 |
| `/proveedores/consultas` | POST | sí (header `X-API-Key`) | 200, 401, 422 (CUIT inválido), 503 (sin claves configuradas) |
| `/proveedores/{cuit}/bcra` | GET | sí | 200, 401, 404 (sin datos en BCRA), 422, 502 (BCRA caído) |
| `/proveedores/evaluar` | POST | sí | 200, 401, 422, 502 |

```bash
curl -X POST http://127.0.0.1:8000/proveedores/consultas \
     -H "X-API-Key: clave-tp-programacion2" -H "Content-Type: application/json" \
     -d '{"cuit": "30500010912",
          "datos_bcra": {"denominacion": "EMPRESA S.A.", "periodos": [{"periodo": "202509",
                         "entidades": [{"entidad": "BANCO A", "situacion": 1}, {"entidad": "BANCO B", "situacion": 3}]}]}}'
```

Respuesta:

```json
{
  "decision": "Revisar",
  "situacion_deudas": {"situacion_1": 1, "situacion_2": 0, "situacion_3": 1, "situacion_4": 0, "situacion_5": 0},
  "motivo": "Tiene deudas en situación 2, 3 o 4 (1 en situación 3)."
}
```

## Estructura

| Carpeta | Contenido |
|---|---|
| `config/` | Configuración leída de variables de entorno (`.env`) |
| `scraping/` | robots.txt, descarga, parseo con BeautifulSoup, filtros, Boletín Oficial |
| `apis/` | Cliente del BCRA, consulta del CUIT en ARCA y cliente de nuestra API |
| `api_propia/` | Servidor FastAPI: autenticación por API key, modelos Pydantic, endpoints |
| `proveedores/` | Validación de CUIT, verificación en ARCA, reglas de decisión (`decision.py`), consulta (`consulta.py`), scoring de riesgo, documentos, textos |
| `web_info/` | Fuentes web usadas, dominio e IP |
| `etl/` | Funciones de Pandas: arma una tabla, la limpia, la resume y la guarda en CSV |
| `reportes/` | Excel de cada consulta, armado con Pandas (`consulta_excel.py`) |
| `correo/` | Envío del Excel por mail con `smtplib` (`enviar.py`) |
| `docs/` | Evidencia de la inspección del HTML |
| `tests/` | 141 pruebas con `unittest` (fixtures sintéticos; BCRA, ARCA y servidor de correo simulados) |

## Cumplimiento de las necesidades funcionales

| N | Necesidad | Dónde se cumple |
|---|---|---|
| N01 | Entorno Python y módulos | Carpetas por módulo, `requirements.txt`, entorno virtual, `.env` y `config/ajustes.py` |
| N02 | Puntajes con operadores (riesgo, cumplimiento documental, vencimientos, incidencias) | `proveedores/scoring.py`, `proveedores/documentos.py` |
| N03 | Clasificación con estructuras de control | `proveedores/decision.py` (Aceptar / Revisar / Rechazar) y `clasificar_proveedor` (habilitado, observado, requiere revisión, suspendido) |
| N04 | Funciones: validar CUIT, limpiar razón social, evaluar documentos, consolidar indicadores | `proveedores/validaciones.py`, `textos.py`, `documentos.py`, `scoring.evaluar_proveedor` |
| N05 | Listas: proveedores críticos, dominios permitidos, expedientes, palabras clave legales, destinatarios | `PROVEEDORES_CRITICOS`, `DOMINIOS_PERMITIDOS`, `DESTINATARIOS_COMITE` (config), `PALABRAS_CLAVE_LEGALES` (textos), `listar_expedientes` (scraping) |
| N06 | Diccionarios: estados documentales, ponderaciones, credenciales, parámetros HTTP | `ESTADOS_DOCUMENTALES`, `PARAMETROS_HTTP`, credenciales por entorno (config), `PONDERACIONES` (scoring) |
| N07 | Cadenas: normalizar razón social, extraer expedientes, preparar observaciones | `normalizar_razon_social`, `extraer_codigo_expediente`, `extraer_adjudicatarios`, `preparar_observacion` |
| N08 | Sitio web, URL, DNS e IP de las fuentes | `web_info/fuentes.py` |
| N09 | Inspección manual del HTML | `docs/inspeccion_html_boletin_oficial.md` |
| N10 | Scraping con requests y BeautifulSoup (términos de uso, robots.txt, frecuencia) | `scraping/robots.py`, `descargar.py`, `parsear.py`, `boletin_oficial.py`; se usa en el paso 4 del flujo |
| N11 | Recuperar texto, href, src, class, id y data-* | `scraping/busquedas.py` (`extraer_valores`), `parsear.py` |
| N12 | `find_all` por etiqueta, clase, id, atributos, texto, lambda y combinaciones | `scraping/busquedas.py` |
| N13 | API pública y diferencia con API privada | `apis/bcra.py` (API pública del BCRA) y la sección de decisiones de este README |
| N14–N17 | JSON, GET/POST, `requests` con status codes, timeout y errores, API key en header | BCRA, ARCA y nuestra API (`api_propia/`, `apis/`) |
| N19–N22 | ETL con Pandas: DataFrame, tipos, nulos, CSV y agrupación (`groupby`) | `etl/basico.py` (`armar_tabla`, `limpiar`, `guardar_csv`, `resumir_por_estado`) |
| Excel | Exportar el detalle de la consulta a `.xlsx` con Pandas (`to_excel`, motor `openpyxl`) | `reportes/consulta_excel.py` |
| N24–N25 | Enviar un correo con adjunto (`smtplib`, `EmailMessage`); SMTP / POP3 / IMAP y credenciales fuera del código | `correo/enviar.py`, `.env.example` |

## Decisiones importantes

- **API pública vs. privada.** La API del BCRA es pública: no pide autenticación, sólo limita tráfico por IP.
  La autenticación está en **nuestra** API (API key en el header `X-API-Key`, guardada en variables de
  entorno, comparada con `secrets.compare_digest`).
- **Métodos HTTP.** Se usa GET para consultar y POST para enviar datos a procesar. PUT/PATCH/DELETE no se usan
  porque la API no guarda datos.
- **CUIT.** Se valida largo y dígito verificador (módulo 11) antes de consultar.
- **Privacidad.** El programa y la API aceptan empresas y personas humanas, siempre que el CUIT esté activo en ARCA (el Boletín solo trae personas jurídicas, así que una persona humana nunca figura ahí).
  El Excel no incluye domicilio ni otros datos personales: solo razón social, CUIT, cantidades por situación, condición y los datos del aviso del Boletín.
  El scraping del Boletín se limita a personas jurídicas (CUIT 30, 33 y 34).
- **Sobre la fuente de ARCA.** No es una API pública documentada como la del BCRA: es el servicio que usa la página
  gratuita de FactuARCA (`POST https://api.factuarca.app/v1/tools/padron` con `{"cuit": "..."}`). No pide login ni CAPTCHA
  y su `robots.txt` no restringe nada, pero no tiene garantía de continuidad ni límites publicados. Por eso se consulta de
  a un CUIT por vez, con pausa entre pedidos y User-Agent que identifica el proyecto, y la fuente está aislada en
  `apis/padron_arca.py` para poder reemplazarla. La página del Registro Nacional de Sociedades (argentina.gob.ar)
  **no se usó** porque su buscador por CUIT tiene un CAPTCHA (Cloudflare Turnstile) y no se evade.

## Pruebas

```bash
python -m unittest discover -s tests -t .
```

- ARCA, el BCRA y el servidor de correo se simulan en los tests, así que no dependen de internet. El envío real de mail
  **no se probó** (requiere la contraseña de aplicación de quien lo corre).
- Los tests del scraping usan HTML sintético con la estructura real del Boletín. Si el Boletín cambia su HTML,
  hay que ajustar `scraping/parsear.py`.
- El BCRA limita el tráfico por IP y a veces corta la conexión: el cliente reintenta hasta 3 veces con pausas
  crecientes antes de informar el error.
- Si el BCRA da error de certificado SSL, actualizar `certifi` (`pip install --upgrade certifi`) o apuntar
  `BCRA_CA_BUNDLE` a un bundle de certificados. No se debe desactivar la verificación.
