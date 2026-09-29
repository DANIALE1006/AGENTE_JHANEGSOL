"""
Servicio del Agente 1: Notificador y Auditor de Ventas por Correo.
Responsable de:
  - Generar reportes ejecutivos de ventas (ayer, hoy, a pedido).
  - Enviar correos automáticos programados (8:00 AM y 5:00 PM).
  - Enviar correos a pedido desde la interfaz o por orden del usuario.
  - Mantener historial de envíos.
"""
from __future__ import annotations
import os
import smtplib
from datetime import date, datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

from services.agent_data import (
    limpiar_cache,
    obtener_metricas_ventas_fecha,
    obtener_metricas_ventas_rango,
)

CORREO_DESTINO_DEFAULT = "0331221020@unjfsc.edu.pe"
ZONA_HORARIA = "America/Lima"

# Registro en memoria de envíos realizados
HISTORIAL_ENVIOS: List[Dict[str, Any]] = []


def _obtener_credencial(clave: str, defecto: str = "") -> str:
    """Obtiene credenciales desde st.secrets o variables de entorno."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and clave in st.secrets:
            return str(st.secrets[clave])
    except Exception:
        pass
    return os.getenv(clave, defecto)


def _formatear_moneda(valor: float) -> str:
    return f"S/ {valor:,.2f}"


def construir_cuerpo_reporte(
    periodo: str = "hoy",
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Construye el asunto, texto plano y HTML del correo para el periodo indicado.
    Periodos válidos: 'ayer', 'hoy', 'semana', 'mes', 'personalizado'.
    """
    ahora = datetime.now(ZoneInfo(ZONA_HORARIA))
    hoy = ahora.date()
    ayer = hoy - timedelta(days=1)

    if periodo == "ayer":
        f_ini = ayer
        f_fin = ayer
        titulo_periodo = f"Ventas del Día Anterior ({ayer.strftime('%d/%m/%Y')})"
        asunto_def = f"📊 Reporte Automático 8:00 AM - Ventas del Día Anterior ({ayer.strftime('%d/%m/%Y')})"
    elif periodo == "hoy":
        f_ini = hoy
        f_fin = hoy
        titulo_periodo = f"Cierre de Ventas de Hoy ({hoy.strftime('%d/%m/%Y')})"
        asunto_def = f"📈 Reporte Automático 5:00 PM - Cierre de Ventas de Hoy ({hoy.strftime('%d/%m/%Y')})"
    elif periodo == "semana":
        f_ini = hoy - timedelta(days=7)
        f_fin = hoy
        titulo_periodo = f"Ventas de los Últimos 7 Días ({f_ini.strftime('%d/%m')} al {f_fin.strftime('%d/%m/%Y')})"
        asunto_def = f"📅 Reporte Semanal de Ventas - JHANEGSOL S.A.C."
    elif periodo == "mes":
        f_ini = hoy - timedelta(days=30)
        f_fin = hoy
        titulo_periodo = f"Ventas del Último Mes ({f_ini.strftime('%d/%m')} al {f_fin.strftime('%d/%m/%Y')})"
        asunto_def = f"💼 Reporte Mensual de Facturación - JHANEGSOL S.A.C."
    else:
        f_ini = fecha_inicio or hoy
        f_fin = fecha_fin or hoy
        titulo_periodo = f"Reporte de Ventas ({f_ini.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')})"
        asunto_def = f"📋 Reporte de Ventas a Pedido - JHANEGSOL S.A.C."

    # Obtener métricas reales
    limpiar_cache()
    if f_ini == f_fin:
        metricas = obtener_metricas_ventas_fecha(f_ini)
    else:
        metricas = obtener_metricas_ventas_rango(f_ini, f_fin)

    total_bruto = metricas["total_bruto"]
    total_notas = metricas["total_notas"]
    total_neto = metricas["total_neto"]
    n_ventas = metricas["n_ventas"]
    ticket_prom = metricas["ticket_promedio"]
    igv = metricas["igv_total"]
    subtotal = metricas["subtotal"]
    por_tipo = metricas["por_tipo"]
    top_prods = metricas["top_productos"][:5]

    # Diagnóstico automático del Agente 1
    if n_ventas == 0:
        diagnostico = "ℹ️ No se registraron comprobantes de venta en este período de análisis."
    elif total_bruto > 1000:
        diagnostico = f"🚀 Excelente volumen comercial con {n_ventas} transacciones y recaudación neta de {_formatear_moneda(total_neto)}."
    else:
        diagnostico = f"✅ Actividad comercial normal con {n_ventas} operaciones y ticket promedio de {_formatear_moneda(ticket_prom)}."

    # 1. Texto Plano
    filas_tipo_txt = "\n".join([f"  - {t['tipo_comprobante']}: {t['cantidad']} emitidos | {_formatear_moneda(t['monto'])}" for t in por_tipo]) or "  - Sin registros."
    filas_prod_txt = "\n".join([f"  {i+1}. {p['descripcion']} ({p['codigo']}): {int(p['unidades'])} unid. | {_formatear_moneda(p['ingresos'])}" for i, p in enumerate(top_prods)]) or "  - Sin detalle de ítems."

    cuerpo_texto = f"""JHANEGSOL S.A.C. - AGENTE IA NOTIFICADOR DE VENTAS
==============================================================
{titulo_periodo}
Fecha y hora de emisión: {ahora.strftime('%d/%m/%Y %I:%M %p')}

RESUMEN GENERAL:
--------------------------------------------------------------
- Total Bruto Facturado: {_formatear_moneda(total_bruto)}
- Notas de Crédito emitidas: {_formatear_moneda(total_notas)}
- Ingreso Neto Real: {_formatear_moneda(total_neto)}
- Cantidad de Comprobantes: {n_ventas}
- Ticket Promedio: {_formatear_moneda(ticket_prom)}
- Subtotal Gravado: {_formatear_moneda(subtotal)}
- IGV (18%): {_formatear_moneda(igv)}

DESGLOSE POR TIPO DE COMPROBANTE:
{filas_tipo_txt}

TOP 5 PRODUCTOS MÁS VENDIDOS:
{filas_prod_txt}

DIAGNÓSTICO DEL AGENTE:
{diagnostico}

--------------------------------------------------------------
Reporte generado automáticamente por Agente 1 (Email & Sales)
JHANEGSOL S.A.C. • RUC: 20600000001 • Huacho, Lima
"""

    # 2. HTML profesional con estilos responsivos
    filas_tipo_html = "".join([
        f"<tr><td style='padding:8px 12px;border-bottom:1px solid #E2E8F0;'>{t['tipo_comprobante']}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #E2E8F0;text-align:center;'><b>{t['cantidad']}</b></td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #E2E8F0;text-align:right;'>{_formatear_moneda(t['monto'])}</td></tr>"
        for t in por_tipo
    ]) or "<tr><td colspan='3' style='padding:10px;text-align:center;color:#64748B;'>Sin ventas registradas</td></tr>"

    filas_prod_html = "".join([
        f"<tr><td style='padding:8px 12px;border-bottom:1px solid #E2E8F0;'><b>#{i+1}</b> {p['descripcion']}<br><small style='color:#64748B;'>Cod: {p['codigo']}</small></td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #E2E8F0;text-align:center;'>{int(p['unidades'])}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #E2E8F0;text-align:right;'><b>{_formatear_moneda(p['ingresos'])}</b></td></tr>"
        for i, p in enumerate(top_prods)
    ]) or "<tr><td colspan='3' style='padding:10px;text-align:center;color:#64748B;'>Sin detalle de productos</td></tr>"

    cuerpo_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #F8FAFC; margin: 0; padding: 20px; }}
    .container {{ max-width: 620px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #E2E8F0; box-shadow: 0 4px 6px rgba(0,0,0,0.04); }}
    .header {{ background: linear-gradient(135deg, #0D47A1 0%, #1976D2 100%); color: #ffffff; padding: 24px; }}
    .header h1 {{ margin: 0; font-size: 20px; letter-spacing: 0.5px; }}
    .header p {{ margin: 4px 0 0 0; font-size: 13px; color: #BBDEFB; }}
    .content {{ padding: 24px; }}
    .kpi-grid {{ display: table; width: 100%; margin-bottom: 20px; }}
    .kpi-row {{ display: table-row; }}
    .kpi-card {{ display: table-cell; background: #F1F5F9; border-radius: 8px; padding: 12px; width: 31%; vertical-align: top; border: 1px solid #E2E8F0; }}
    .kpi-card.destacado {{ background: #E8F5E9; border-color: #C8E6C9; }}
    .kpi-label {{ font-size: 11px; text-transform: uppercase; color: #64748B; font-weight: 600; margin-bottom: 4px; }}
    .kpi-val {{ font-size: 18px; font-weight: bold; color: #0F172A; }}
    .kpi-card.destacado .kpi-val {{ color: #1B5E20; }}
    .seccion-titulo {{ font-size: 14px; font-weight: 700; color: #1E293B; margin: 20px 0 10px 0; border-bottom: 2px solid #0D47A1; padding-bottom: 4px; display: inline-block; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 16px; }}
    th {{ background: #F8FAFC; color: #475569; font-weight: 600; text-align: left; padding: 8px 12px; border-bottom: 2px solid #CBD5E1; }}
    .diagnostico {{ background: #EFF6FF; border-left: 4px solid #1D4ED8; padding: 12px 16px; border-radius: 6px; font-size: 13px; color: #1E40AF; margin-top: 16px; }}
    .footer {{ background: #F1F5F9; padding: 16px 24px; font-size: 11px; color: #64748B; text-align: center; border-top: 1px solid #E2E8F0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>📊 JHANEGSOL S.A.C.</h1>
      <p>{titulo_periodo} • {ahora.strftime('%d/%m/%Y %I:%M %p')}</p>
    </div>
    <div class="content">
      <div style="margin-bottom: 18px;">
        <span style="font-size: 12px; font-weight: 600; color: #0D47A1; background: #E3F2FD; padding: 4px 10px; border-radius: 999px;">
          🤖 Agente IA Notificador de Ventas
        </span>
      </div>

      <table style="width: 100%; margin-bottom: 20px;">
        <tr>
          <td style="width: 32%; background: #E8F5E9; border: 1px solid #C8E6C9; border-radius: 8px; padding: 12px; text-align: center;">
            <div style="font-size: 11px; color: #2E7D32; font-weight: bold;">TOTAL NETO</div>
            <div style="font-size: 20px; font-weight: bold; color: #1B5E20; margin-top: 4px;">{_formatear_moneda(total_neto)}</div>
          </td>
          <td style="width: 2%;"></td>
          <td style="width: 32%; background: #F1F5F9; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px; text-align: center;">
            <div style="font-size: 11px; color: #64748B; font-weight: bold;">COMPROBANTES</div>
            <div style="font-size: 20px; font-weight: bold; color: #0F172A; margin-top: 4px;">{n_ventas}</div>
          </td>
          <td style="width: 2%;"></td>
          <td style="width: 32%; background: #F1F5F9; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px; text-align: center;">
            <div style="font-size: 11px; color: #64748B; font-weight: bold;">TICKET PROMEDIO</div>
            <div style="font-size: 20px; font-weight: bold; color: #0F172A; margin-top: 4px;">{_formatear_moneda(ticket_prom)}</div>
          </td>
        </tr>
      </table>

      <div style="font-size: 13px; color: #475569; margin-bottom: 16px;">
        • <b>Total Facturado Bruto:</b> {_formatear_moneda(total_bruto)} &nbsp;|&nbsp; 
        • <b>Notas de Crédito:</b> {_formatear_moneda(total_notas)} &nbsp;|&nbsp; 
        • <b>IGV 18%:</b> {_formatear_moneda(igv)}
      </div>

      <div class="seccion-titulo">Desglose por Comprobante</div>
      <table>
        <thead>
          <tr>
            <th>Tipo</th>
            <th style="text-align:center;">Emitidos</th>
            <th style="text-align:right;">Total (S/)</th>
          </tr>
        </thead>
        <tbody>
          {filas_tipo_html}
        </tbody>
      </table>

      <div class="seccion-titulo">Top 5 Productos Más Vendidos</div>
      <table>
        <thead>
          <tr>
            <th>Producto</th>
            <th style="text-align:center;">Unid.</th>
            <th style="text-align:right;">Ingreso (S/)</th>
          </tr>
        </thead>
        <tbody>
          {filas_prod_html}
        </tbody>
      </table>

      <div class="diagnostico">
        <b>💡 Diagnóstico del Agente IA:</b><br>{diagnostico}
      </div>
    </div>
    <div class="footer">
      JHANEGSOL S.A.C. • RUC: 20600000001 • Huacho, Lima - Perú<br>
      Sistema Comercial e Inteligencia de Negocios Multi-Agente
    </div>
  </div>
</body>
</html>
"""

    return {
        "asunto": asunto_def,
        "titulo_periodo": titulo_periodo,
        "cuerpo_texto": cuerpo_texto,
        "cuerpo_html": cuerpo_html,
        "metricas": metricas,
        "diagnostico": diagnostico,
    }


def enviar_reporte_ventas_email(
    periodo: str = "hoy",
    destinatario: Optional[str] = None,
    asunto_personalizado: Optional[str] = None,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    modo_envio: str = "a_pedido",
) -> Dict[str, Any]:
    """
    Genera y envía por correo electrónico la situación de las ventas.
    Registra el resultado en HISTORIAL_ENVIOS.
    """
    ahora = datetime.now(ZoneInfo(ZONA_HORARIA))

    contenido = construir_cuerpo_reporte(
        periodo=periodo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    asunto = asunto_personalizado or contenido["asunto"]
    destinatario_final = (
        destinatario
        or _obtener_credencial("SMTP_DESTINATARIO")
        or CORREO_DESTINO_DEFAULT
    ).strip()

    smtp_server = _obtener_credencial("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(_obtener_credencial("SMTP_PORT", "465"))
    smtp_user = _obtener_credencial("SMTP_USER", "danielaalejandramv@gmail.com")
    smtp_password = _obtener_credencial("SMTP_PASSWORD")

    # Validación de configuración SMTP
    if not smtp_password:
        msg_err = (
            "❌ No se ha configurado la contraseña de aplicación de Gmail (SMTP_PASSWORD). "
            "Por favor agrégala en Secrets o variables de entorno para habilitar el envío real."
        )
        registro = {
            "timestamp": ahora.strftime("%Y-%m-%d %H:%M:%S"),
            "periodo": periodo,
            "destinatario": destinatario_final,
            "asunto": asunto,
            "modo": modo_envio,
            "exito": False,
            "mensaje": msg_err,
            "resumen": contenido["cuerpo_texto"][:250] + "...",
        }
        HISTORIAL_ENVIOS.insert(0, registro)
        return {
            "exito": False,
            "asunto": asunto,
            "destinatario": destinatario_final,
            "mensaje": msg_err,
            "contenido": contenido,
        }

    # Armado del correo multiparte (texto plano + HTML)
    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_user
    msg["To"] = destinatario_final
    msg["Subject"] = asunto

    msg.attach(MIMEText(contenido["cuerpo_texto"], "plain", "utf-8"))
    msg.attach(MIMEText(contenido["cuerpo_html"], "html", "utf-8"))

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
            server.starttls()

        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, destinatario_final, msg.as_string())
        server.quit()

        msg_exito = f"✅ Correo de situación de ventas enviado exitosamente a {destinatario_final}."
        registro = {
            "timestamp": ahora.strftime("%Y-%m-%d %H:%M:%S"),
            "periodo": periodo,
            "destinatario": destinatario_final,
            "asunto": asunto,
            "modo": modo_envio,
            "exito": True,
            "mensaje": msg_exito,
            "resumen": contenido["cuerpo_texto"][:250] + "...",
        }
        HISTORIAL_ENVIOS.insert(0, registro)
        return {
            "exito": True,
            "asunto": asunto,
            "destinatario": destinatario_final,
            "mensaje": msg_exito,
            "contenido": contenido,
        }
    except Exception as e:
        msg_err = f"❌ Error al enviar correo SMTP a {destinatario_final}: {e}"
        registro = {
            "timestamp": ahora.strftime("%Y-%m-%d %H:%M:%S"),
            "periodo": periodo,
            "destinatario": destinatario_final,
            "asunto": asunto,
            "modo": modo_envio,
            "exito": False,
            "mensaje": msg_err,
            "resumen": contenido["cuerpo_texto"][:250] + "...",
        }
        HISTORIAL_ENVIOS.insert(0, registro)
        return {
            "exito": False,
            "asunto": asunto,
            "destinatario": destinatario_final,
            "mensaje": msg_err,
            "contenido": contenido,
        }


def obtener_historial_envios() -> List[Dict[str, Any]]:
    """Retorna la lista de los últimos envíos registrados."""
    return HISTORIAL_ENVIOS[:30]
