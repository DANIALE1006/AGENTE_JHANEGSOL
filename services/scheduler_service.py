"""
Programador de tareas en segundo plano para el Agente 1 (Email & Ventas).
Ejecuta automáticamente:
  - 8:00 AM: Reporte de ventas del día anterior (ayer).
  - 5:00 PM: Reporte de ventas del día actual (hoy).
Zona Horaria: America/Lima (Perú).
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from services.email_agent_service import enviar_reporte_ventas_email

_scheduler: Optional[BackgroundScheduler] = None
ZONA_HORARIA = "America/Lima"


def reportar_cierre_ayer_8am():
    """Genera y envía automáticamente el reporte de ventas del DÍA ANTERIOR a las 8:00 AM."""
    print("[Agente 1] Ejecutando reporte programado de las 8:00 AM (Ventas de ayer)...")
    res = enviar_reporte_ventas_email(
        periodo="ayer",
        modo_envio="automático_8am",
    )
    print(f"[Agente 1] Resultado envío 8:00 AM: {res.get('mensaje')}")
    return res


def reportar_cierre_hoy_5pm():
    """Genera y envía automáticamente el reporte de ventas del DÍA ACTUAL a las 5:00 PM."""
    print("[Agente 1] Ejecutando reporte programado de las 5:00 PM (Cierre de hoy)...")
    res = enviar_reporte_ventas_email(
        periodo="hoy",
        modo_envio="automático_5pm",
    )
    print(f"[Agente 1] Resultado envío 5:00 PM: {res.get('mensaje')}")
    return res


def iniciar_programador() -> BackgroundScheduler:
    """Inicia las tareas programadas en segundo plano con protección contra duplicados."""
    global _scheduler
    if _scheduler is None or not _scheduler.running:
        tz = ZoneInfo(ZONA_HORARIA)
        _scheduler = BackgroundScheduler(timezone=tz)

        # 1. Job 8:00 AM - Ventas del día anterior
        _scheduler.add_job(
            reportar_cierre_ayer_8am,
            CronTrigger(hour=8, minute=0, timezone=tz),
            id="reporte_ventas_ayer_8am",
            name="Reporte 8:00 AM - Ventas Día Anterior",
            replace_existing=True,
        )

        # 2. Job 5:00 PM (17:00 hs) - Ventas de hoy
        _scheduler.add_job(
            reportar_cierre_hoy_5pm,
            CronTrigger(hour=17, minute=0, timezone=tz),
            id="reporte_ventas_hoy_5pm",
            name="Reporte 5:00 PM - Cierre Ventas Hoy",
            replace_existing=True,
        )

        _scheduler.start()
        print("[Agente 1] Programador iniciado: 8:00 AM (Ayer) y 5:00 PM (Hoy) - America/Lima.")
    return _scheduler


def obtener_estado_scheduler() -> Dict[str, Any]:
    """Retorna información detallada sobre el estado del programador de tareas."""
    tz = ZoneInfo(ZONA_HORARIA)
    ahora = datetime.now(tz)
    activo = _scheduler is not None and _scheduler.running

    prox_8am_str = "No programado"
    prox_5pm_str = "No programado"

    if activo:
        for job in _scheduler.get_jobs():
            if job.id == "reporte_ventas_ayer_8am" and job.next_run_time:
                prox_8am_str = job.next_run_time.strftime("%d/%m/%Y %I:%M %p")
            elif job.id == "reporte_ventas_hoy_5pm" and job.next_run_time:
                prox_5pm_str = job.next_run_time.strftime("%d/%m/%Y %I:%M %p")

    return {
        "activo": activo,
        "zona_horaria": ZONA_HORARIA,
        "hora_actual": ahora.strftime("%d/%m/%Y %I:%M:%S %p"),
        "proxima_8am": prox_8am_str,
        "proxima_5pm": prox_5pm_str,
        "scheduler_instance": _scheduler,
    }


def ejecutar_disparo_8am_inmediato() -> Dict[str, Any]:
    """Permite probar o forzar el envío que corresponde a las 8:00 AM (ventas de ayer)."""
    return reportar_cierre_ayer_8am()


def ejecutar_disparo_5pm_inmediato() -> Dict[str, Any]:
    """Permite probar o forzar el envío que corresponde a las 5:00 PM (ventas de hoy)."""
    return reportar_cierre_hoy_5pm()
