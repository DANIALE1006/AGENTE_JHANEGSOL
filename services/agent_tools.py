# Destinatario fijo por defecto
CORREO_DESTINO = "dmondragonv1006@gmail.com"


def enviar_correo_gmail(asunto: str, cuerpo: str, destinatario: str = CORREO_DESTINO) -> Resultado:
    """Envía un correo electrónico desde la cuenta institucional usando SMTP SSL (Puerto 465)."""
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 465))
    smtp_user = os.getenv("SMTP_USER", "0331221020@unjfsc.edu.pe")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not smtp_password:
        return {
            "titulo": "Envío de correo",
            "resumen": "❌ Error: No se ha configurado la contraseña de aplicación (SMTP_PASSWORD) en las variables de entorno."
        }

    destinatario_final = destinatario or CORREO_DESTINO

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = destinatario_final
    msg['Subject'] = asunto
    msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, destinatario_final, msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, destinatario_final, msg.as_string())

        return {
            "titulo": "Envío de correo",
            "resumen": f"✅ Correo enviado exitosamente a {destinatario_final} desde {smtp_user}."
        }
    except smtplib.SMTPAuthenticationError:
        return {
            "titulo": "Envío de correo",
            "resumen": f"❌ Error de autenticación: Verifica que la Contraseña de Aplicación de 16 caracteres para la cuenta {smtp_user} sea correcta."
        }
    except Exception as e:
        return {
            "titulo": "Envío de correo",
            "resumen": f"❌ Error de conexión al enviar el correo a {destinatario_final}: {e}"
        }
