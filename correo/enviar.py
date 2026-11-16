import mimetypes
import os
import smtplib
import ssl
from email.message import EmailMessage

from config import ajustes


class ErrorCorreo(Exception):
    pass


def armar_mensaje(remitente, destinatario, asunto, cuerpo, ruta_adjunto=None):
    mensaje = EmailMessage()
    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)

    if ruta_adjunto:
        tipo, _ = mimetypes.guess_type(ruta_adjunto)
        principal, secundario = (tipo or "application/octet-stream").split("/", 1)
        with open(ruta_adjunto, "rb") as archivo:
            mensaje.add_attachment(archivo.read(), maintype=principal, subtype=secundario,
                                   filename=os.path.basename(ruta_adjunto))
    return mensaje


def enviar(destinatario, asunto, cuerpo, ruta_adjunto=None):
    if not ajustes.SMTP_USUARIO or not ajustes.SMTP_CLAVE:
        raise ErrorCorreo(
            "Faltan SMTP_USUARIO y SMTP_CLAVE en el .env (cuenta desde la que se envían los mails). "
            "Con Gmail la clave es una contraseña de aplicación."
        )
    if not destinatario:
        raise ErrorCorreo("No se indicó el mail de destino.")
    mensaje = armar_mensaje(ajustes.SMTP_USUARIO, destinatario, asunto, cuerpo, ruta_adjunto)

    try:
        with smtplib.SMTP(ajustes.SMTP_SERVIDOR, ajustes.SMTP_PUERTO, timeout=30) as servidor:
            servidor.starttls(context=ssl.create_default_context())
            servidor.login(ajustes.SMTP_USUARIO, ajustes.SMTP_CLAVE)
            servidor.send_message(mensaje)
    except smtplib.SMTPAuthenticationError as error:
        raise ErrorCorreo(
            "El servidor de correo rechazó el usuario o la clave. Con Gmail hay que usar una "
            "contraseña de aplicación, no la clave normal de la cuenta."
        ) from error
    except (smtplib.SMTPException, OSError) as error:
        raise ErrorCorreo(f"No se pudo enviar el correo: {error}") from error
    return destinatario
