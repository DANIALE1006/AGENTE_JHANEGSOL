from apscheduler.schedulers.background import BackgroundScheduler
from services.agent_tools import enviar_correo_gmail, resumen_ventas

# Variable de control para evitar duplicar el programador
_scheduler = None

def reportar_cierre_ayer_8am():
    """Genera y envía por correo el resumen de las ventas del día anterior a las 8:00 AM."""
    resultado = resumen_ventas(dias=1)
    asunto = "📊 Reporte 8:00 AM - Ventas del Día Anterior"
    cuerpo = f"Hola,\n\nEste es el reporte de cierre de ventas del día anterior:\n\n{resultado['resumen']}\n\nSaludos,\nAgente IA Jhanegsol"
    enviar_correo_gmail(asunto=asunto, cuerpo=cuerpo)

def reportar_cierre_hoy_5pm():
    """Genera y envía por correo el resumen de las ventas del día actual a las 5:00 PM."""
    resultado = resumen_ventas(dias=1)
    asunto = "📈 Reporte 5:00 PM - Cierre de Ventas de Hoy"
    cuerpo = f"Hola,\n\nEste es el reporte del cierre de jornada de hoy:\n\n{resultado['resumen']}\n\nSaludos,\nAgente IA Jhanegsol"
    enviar_correo_gmail(asunto=asunto, cuerpo=cuerpo)

def iniciar_programador():
    """Inicia las tareas programadas en segundo plano."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="America/Lima")
        # Programar a las 8:00 AM de lunes a domingo
        _scheduler.add_job(reportar_cierre_ayer_8am, 'cron', hour=8, minute=0)
        # Programar a las 5:00 PM (17:00 hs) de lunes a domingo
        _scheduler.add_job(reportar_cierre_hoy_5pm, 'cron', hour=17, minute=0)
        _scheduler.start()
        print("⏰ Programador de reportes (8:00 AM y 5:00 PM) iniciado correctamente.")
