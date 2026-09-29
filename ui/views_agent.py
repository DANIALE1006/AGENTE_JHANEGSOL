"""
Vista Central del Sistema Multi-Agente IA - JHANEGSOL S.A.C.
Integra 3 agentes inteligentes:
  1. Agente 1: Notificador y Auditor de Ventas por Correo (Automático 8:00 AM y 5:00 PM + Envíos a Pedido).
  2. Agente 2: Generador de Informes Gráficos y Reportes Descargables en PDF.
  3. Agente 3: Consultor Comercial Q&A (Preguntas y Respuestas, Diagnóstico y Simulador).
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.pdf_service import mostrar_previsualizacion_pdf
from services.agent_brain import ESTILOS, ia_disponible, proveedor_ia, responder
from services.agent_data import (
    cargar_productos,
    cargar_comprobantes,
    cargar_detalle_ventas,
    limpiar_cache,
    obtener_metricas_ventas_fecha,
    obtener_metricas_ventas_rango,
)
from services.agent_tools import (
    analisis_margenes,
    productos_bajo_stock,
    productos_sin_movimiento,
    sugerir_reposicion,
    _demanda_diaria,
)
from services.email_agent_service import (
    CORREO_DESTINO_DEFAULT,
    construir_cuerpo_reporte,
    enviar_reporte_ventas_email,
    obtener_historial_envios,
    probar_conexion_smtp,
    _obtener_credencial,
)
from services.report_pdf_service import (
    generar_pdf_informe_inventario,
    generar_pdf_informe_ventas,
)
from services.scheduler_service import (
    ejecutar_disparo_5pm_inmediato,
    ejecutar_disparo_8am_inmediato,
    iniciar_programador,
    obtener_estado_scheduler,
)
from ui.components import render_header

AZUL = "#0D47A1"
AZUL_LIGHT = "#1565C0"
VERDE = "#2E7D32"
NARANJA = "#F57C00"
ZONA_HORARIA = "America/Lima"

ACCESOS_RAPIDOS = [
    ("📦", "Resumen del inventario"),
    ("🚨", "¿Qué productos están bajo stock?"),
    ("🛒", "¿Qué debo reponer?"),
    ("💰", "Ventas del último mes"),
    ("🏆", "Productos más vendidos"),
    ("🅰️", "Análisis ABC de productos"),
    ("🐢", "Productos sin movimiento"),
    ("📈", "¿Cómo están mis márgenes?"),
    ("👥", "¿Quiénes son mis mejores clientes?"),
    ("📅", "Ventas de hoy"),
    ("📧", "Enviar correo con las ventas de hoy"),
    ("📊", "Generar informe en PDF"),
]

CSS = """
<style>
.agente-hub-header {
    background: linear-gradient(120deg, #0D47A1 0%, #1565C0 50%, #1976D2 100%);
    border-radius: 16px;
    padding: 22px 26px;
    color: #fff;
    margin-bottom: 20px;
    box-shadow: 0 4px 12px rgba(13, 71, 161, 0.15);
}
.agente-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-top: 14px;
}
.agente-mini-card {
    background: rgba(255, 255, 255, 0.12);
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 12px;
    padding: 14px 16px;
    color: #fff;
}
.agente-mini-card h4 {
    margin: 0 0 4px 0;
    font-size: 1rem;
    color: #FFFFFF;
}
.agente-mini-card p {
    margin: 0;
    font-size: 0.82rem;
    color: #E3F2FD;
    line-height: 1.35;
}
.badge-status {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
}
.badge-activo { background: #C8E6C9; color: #1B5E20; }
.badge-inactivo { background: #FFCDD2; color: #B71C1C; }
.badge-info { background: #E1F5FE; color: #0277BD; }
.panel-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 18px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    margin-bottom: 16px;
}
.kpi-box {
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 14px;
    text-align: center;
}
.kpi-box-num {
    font-size: 1.4rem;
    font-weight: 700;
    color: #0D47A1;
    margin-top: 2px;
}
.kpi-box-lbl {
    font-size: 0.75rem;
    font-weight: 600;
    color: #64748B;
    text-transform: uppercase;
}
.tarjeta {
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 14px;
    background: #fff;
    height: 100%;
}
.tarjeta h4 { margin: 0 0 4px 0; font-size: 0.95rem; }
.tarjeta p { margin: 0; font-size: 0.85rem; color: #475569; }
</style>
"""


# ─────────────────────────── UTILIDADES GRÁFICAS (PLOTLY) ───────────────────────────

def _grafico(spec: dict, clave: str) -> None:
    datos = pd.DataFrame(spec.get("datos") or [])
    if datos.empty:
        return
    tipo, x, y = spec.get("tipo"), spec.get("x"), spec.get("y")
    fig = go.Figure()
    if tipo == "bar":
        fig.add_bar(x=datos[x], y=datos[y], marker_color=AZUL)
    elif tipo == "line":
        fig.add_scatter(x=datos[x], y=datos[y], mode="lines+markers", line=dict(color=AZUL, width=3),
                        fill="tozeroy", fillcolor="rgba(13,71,161,.1)")
    elif tipo == "hist":
        fig.add_histogram(x=datos[x], marker_color=AZUL, nbinsx=20)
    elif tipo == "pareto":
        fig.add_bar(x=datos[x], y=datos[y], name="Ingresos", marker_color=AZUL)
        fig.add_scatter(x=datos[x], y=datos[spec["y2"]], name="% acumulado", yaxis="y2",
                        mode="lines+markers", line=dict(color=NARANJA))
        fig.update_layout(yaxis2=dict(overlaying="y", side="right", range=[0, 105], ticksuffix="%"))
        fig.add_hline(y=80, line_dash="dot", line_color=NARANJA, yref="y2")
    fig.update_layout(title=spec.get("titulo", ""), height=340, margin=dict(l=10, r=10, t=45, b=10),
                      plot_bgcolor="rgba(0,0,0,0)", showlegend=(tipo == "pareto"))
    st.plotly_chart(fig, use_container_width=True, key=f"graf_{clave}")


def _mostrar_resultados(usados: list, clave: str) -> None:
    for i, u in enumerate(usados):
        r = u["resultado"]
        with st.expander(f"🔧 Acción / Datos: **{r.get('titulo', u['nombre'])}**", expanded=(i == 0)):
            if r.get("grafico"):
                _grafico(r["grafico"], f"{clave}_{i}")
            if r.get("tabla"):
                df = pd.DataFrame(r["tabla"])
                st.dataframe(df, use_container_width=True, hide_index=True, key=f"tab_{clave}_{i}")
                st.download_button("📥 Descargar CSV", df.to_csv(index=False).encode("utf-8"),
                                   file_name=f"{u['nombre']}.csv", mime="text/csv", key=f"dl_{clave}_{i}")
            st.caption(f"Herramienta ejecutada: `{u['nombre']}` · parámetros: `{u['args'] or 'por defecto'}`")


# ─────────────────────────── PESTAÑA: AGENTE 1 (EMAIL & VENTAS) ───────────────────────────

def _tab_agente_email() -> None:
    st.markdown("### ✉️ Agente 1: Notificador de Ventas por Correo")
    st.caption("Monitorea la recaudación diaria y envía reportes ejecutivos por correo a las 8:00 AM (ayer), a las 5:00 PM (hoy) o a solicitud.")

    # 1. ESTADO DEL PROGRAMADOR AUTOMÁTICO (SCHEDULER)
    st.markdown("#### ⏰ Servicio de Envíos Automáticos Diarios")
    estado = obtener_estado_scheduler()
    ahora_pe = datetime.now(ZoneInfo(ZONA_HORARIA))

    c1, c2, c3 = st.columns([1.5, 2, 2])
    with c1:
        if estado["activo"]:
            st.markdown("<span class='badge-status badge-activo'>🟢 Programador Activo</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span class='badge-status badge-inactivo'>🔴 Programador Pausado</span>", unsafe_allow_html=True)
        st.write(f"**Hora Perú (America/Lima):** `{ahora_pe.strftime('%I:%M:%S %p')}`")

    with c2:
        st.info(f"**🌅 Próximo Reporte 8:00 AM (Ayer):**\n\n`{estado['proxima_8am']}`")

    with c3:
        st.info(f"**🌇 Próximo Reporte 5:00 PM (Hoy):**\n\n`{estado['proxima_5pm']}`")

    # Botones para probar / forzar envíos
    st.markdown("##### ⚡ Pruebas y Disparos Inmediatos")
    cb1, cb2, cb3 = st.columns([1.5, 1.5, 1])
    with cb1:
        if st.button("📤 Probar envío 8:00 AM ahora (Ayer)", use_container_width=True, help="Ejecuta la rutina que envía el corte del día anterior"):
            with st.spinner("El Agente 1 está generando y enviando el reporte de ayer..."):
                res = ejecutar_disparo_8am_inmediato()
                if res.get("exito"):
                    st.success(res["mensaje"])
                else:
                    st.warning(res["mensaje"])
                st.rerun()

    with cb2:
        if st.button("📤 Probar envío 5:00 PM ahora (Hoy)", use_container_width=True, help="Ejecuta la rutina que envía el cierre del día actual"):
            with st.spinner("El Agente 1 está generando y enviando el reporte de hoy..."):
                res = ejecutar_disparo_5pm_inmediato()
                if res.get("exito"):
                    st.success(res["mensaje"])
                else:
                    st.warning(res["mensaje"])
                st.rerun()

    with cb3:
        if not estado["activo"]:
            if st.button("▶️ Iniciar Scheduler", use_container_width=True):
                iniciar_programador()
                st.success("Programador iniciado exitosamente.")
                st.rerun()

    st.divider()

    # CONFIGURACIÓN Y DIAGNÓSTICO SMTP GMAIL
    with st.expander("⚙️ Configuración y Diagnóstico de Cuenta Gmail (SMTP)", expanded=False):
        st.markdown(
            "Configura las credenciales de Gmail para el envío de correos. "
            "Google requiere obligatoriamente una **Contraseña de Aplicación** de 16 caracteres "
            "(generada con la 'Verificación en dos pasos' activada en tu cuenta Google)."
        )
        sc1, sc2 = st.columns(2)
        with sc1:
            cfg_user = st.text_input(
                "Correo Emisor (Gmail)",
                value=st.session_state.get("smtp_user") or _obtener_credencial("SMTP_USER", "dmondragonv1006@gmail.com"),
                key="cfg_smtp_user"
            )
            cfg_pass = st.text_input(
                "Contraseña de Aplicación (16 letras)",
                value=st.session_state.get("smtp_password") or _obtener_credencial("SMTP_PASSWORD", ""),
                type="password",
                help="Genera esta clave de 16 letras en: https://myaccount.google.com/apppasswords",
                placeholder="xxxx yyyy zzzz wwww",
                key="cfg_smtp_pass"
            )
        with sc2:
            puerto_actual = int(_obtener_credencial("SMTP_PORT", "587"))
            cfg_port_str = st.radio(
                "Puerto SMTP Preferido",
                ["587 (STARTTLS - Recomendado)", "465 (SSL Directo)"],
                index=0 if puerto_actual == 587 else 1,
                key="cfg_smtp_port_radio"
            )
            cfg_port = 587 if "587" in cfg_port_str else 465
            st.caption("💡 *El puerto 587 con STARTTLS evita el error 'Connection unexpectedly closed' en conexiones residenciales y móviles.*")

            if st.button("🧪 Probar Conexión SMTP y Guardar", use_container_width=True):
                with st.spinner("Probando autenticación con servidores de Gmail..."):
                    ok_smtp, msg_smtp = probar_conexion_smtp(cfg_user, cfg_pass, smtp_port=cfg_port)
                    if ok_smtp:
                        st.session_state["smtp_user"] = cfg_user.strip()
                        st.session_state["smtp_password"] = cfg_pass.replace(" ", "").strip()
                        st.session_state["smtp_port"] = cfg_port
                        st.success(msg_smtp)
                    else:
                        st.error(msg_smtp)

        st.info(
            "🔑 **¿Cómo obtener la Contraseña de Aplicación de 16 caracteres de Google?**\n\n"
            "1. Ingresa a tu cuenta de Google y activa la **Verificación en dos pasos** en [Seguridad de Google](https://myaccount.google.com/security).\n"
            "2. Ve a [Contraseñas de aplicaciones](https://myaccount.google.com/apppasswords).\n"
            "3. En 'Nombre de la app', escribe `Agente Jhanegsol` y haz clic en **Crear**.\n"
            "4. Google te mostrará un recuadro amarillo con 16 letras (ej. `abcd efgh ijkl mnop`). Cópialo y pégalo en el campo superior."
        )

    st.divider()

    # 2. ENVÍO A PEDIDO (ON-DEMAND)
    st.markdown("#### 📋 Solicitar Envío de Reporte a Pedido")
    st.caption("Configura el período y destinatario para enviar la situación de ventas inmediatamente:")

    co1, co2 = st.columns([1.2, 2])
    with co1:
        opcion_periodo = st.selectbox(
            "Período del Reporte",
            [
                "Ventas de Hoy",
                "Ventas del Día Anterior (Ayer)",
                "Últimos 7 Días (Semanal)",
                "Últimos 30 Días (Mensual)",
                "Rango Personalizado",
            ],
            index=0,
            key="email_periodo_sel"
        )

        periodo_map = {
            "Ventas de Hoy": "hoy",
            "Ventas del Día Anterior (Ayer)": "ayer",
            "Últimos 7 Días (Semanal)": "semana",
            "Últimos 30 Días (Mensual)": "mes",
            "Rango Personalizado": "personalizado",
        }
        periodo_cod = periodo_map[opcion_periodo]

        f_ini, f_fin = None, None
        if periodo_cod == "personalizado":
            c_d1, c_d2 = st.columns(2)
            f_ini = c_d1.date_input("Desde", ahora_pe.date() - timedelta(days=7))
            f_fin = c_d2.date_input("Hasta", ahora_pe.date())

        destinatario = st.text_input(
            "Correo del Destinatario",
            value=CORREO_DESTINO_DEFAULT,
            help="Correo donde se enviará el informe. Por defecto: correo institucional.",
            key="email_dest_input"
        )

        asunto_custom = st.text_input(
            "Asunto (Opcional)",
            value="",
            placeholder="Dejar vacío para asunto automático con emojis",
            key="email_asunto_input"
        )

        btn_enviar = st.button("🚀 Enviar Correo Ahora", type="primary", use_container_width=True)

    with co2:
        st.markdown("**👁️ Previsualización del Contenido a Enviar:**")
        contenido_prev = construir_cuerpo_reporte(
            periodo=periodo_cod,
            fecha_inicio=f_ini,
            fecha_fin=f_fin,
        )

        # KPIs resumidos
        m = contenido_prev["metricas"]
        kp1, kp2, kp3, kp4 = st.columns(4)
        kp1.metric("Total Neto", f"S/ {m['total_neto']:,.2f}")
        kp2.metric("Total Facturado", f"S/ {m['total_bruto']:,.2f}")
        kp3.metric("Comprobantes", f"{m['n_ventas']}")
        kp4.metric("Ticket Prom.", f"S/ {m['ticket_promedio']:,.2f}")

        with st.expander("📄 Ver diseño del correo (HTML)", expanded=True):
            st.components.v1.html(contenido_prev["cuerpo_html"], height=380, scrolling=True)

    if btn_enviar:
        with st.spinner("Enviando correo vía SMTP..."):
            usr_override = st.session_state.get("smtp_user")
            pwd_override = st.session_state.get("smtp_password")
            port_override = st.session_state.get("smtp_port")

            resultado = enviar_reporte_ventas_email(
                periodo=periodo_cod,
                destinatario=destinatario,
                asunto_personalizado=asunto_custom if asunto_custom.strip() else None,
                fecha_inicio=f_ini,
                fecha_fin=f_fin,
                modo_envio="a_pedido",
                smtp_user_override=usr_override,
                smtp_password_override=pwd_override,
                smtp_port_override=port_override,
            )
            if resultado.get("exito"):
                st.balloons()
                st.success(resultado["mensaje"])
            else:
                st.error(resultado["mensaje"])

    st.divider()

    # 3. HISTORIAL DE ENVÍOS
    st.markdown("#### 📜 Historial de Envíos Realizados por el Agente 1")
    historial = obtener_historial_envios()
    if historial:
        df_hist = pd.DataFrame(historial)
        cols_mostrar = [c for c in ["timestamp", "periodo", "modo", "destinatario", "exito", "asunto"] if c in df_hist.columns]
        st.dataframe(df_hist[cols_mostrar], use_container_width=True, hide_index=True)
    else:
        st.info("Aún no se registran envíos de correo en esta sesión. Los disparos de las 8:00 AM y 5:00 PM y los envíos manuales aparecerán aquí.")


# ─────────────────────────── PESTAÑA: AGENTE 2 (GRÁFICOS Y PDF) ───────────────────────────

def _tab_agente_graficos_pdf() -> None:
    st.markdown("### 📊 Agente 2: Informes Gráficos y Reportes PDF")
    st.caption("Genera análisis visuales interactivos y compila informes ejecutivos oficiales en formato PDF de alta resolución listos para descargar.")

    ahora_pe = datetime.now(ZoneInfo(ZONA_HORARIA))

    # Selector de período para los gráficos
    c_f1, c_f2 = st.columns([2, 3])
    with c_f1:
        rango_opcion = st.selectbox(
            "Ventana de Análisis",
            ["Últimos 7 días", "Últimos 15 días", "Últimos 30 días", "Últimos 90 días", "Rango personalizado"],
            index=2,
            key="pdf_rango_sel"
        )
        if rango_opcion == "Últimos 7 días":
            f_desde = ahora_pe.date() - timedelta(days=7)
            f_hasta = ahora_pe.date()
        elif rango_opcion == "Últimos 15 días":
            f_desde = ahora_pe.date() - timedelta(days=15)
            f_hasta = ahora_pe.date()
        elif rango_opcion == "Últimos 30 días":
            f_desde = ahora_pe.date() - timedelta(days=30)
            f_hasta = ahora_pe.date()
        elif rango_opcion == "Últimos 90 días":
            f_desde = ahora_pe.date() - timedelta(days=90)
            f_hasta = ahora_pe.date()
        else:
            c_p1, c_p2 = st.columns(2)
            f_desde = c_p1.date_input("Desde", ahora_pe.date() - timedelta(days=30), key="graf_desde")
            f_hasta = c_p2.date_input("Hasta", ahora_pe.date(), key="graf_hasta")

    metricas = obtener_metricas_ventas_rango(f_desde, f_hasta)
    prods = cargar_productos()

    with c_f2:
        st.markdown(f"**Resumen Ejecutivo del Período ({f_desde.strftime('%d/%m/%Y')} al {f_hasta.strftime('%d/%m/%Y')}):**")
        kp1, kp2, kp3 = st.columns(3)
        kp1.metric("Recaudación Neta", f"S/ {metricas['total_neto']:,.2f}")
        kp2.metric("Comprobantes", f"{metricas['n_ventas']}")
        kp3.metric("Ticket Promedio", f"S/ {metricas['ticket_promedio']:,.2f}")

    st.divider()

    # 1. GRÁFICOS INTERACTIVOS (PLOTLY)
    st.markdown("#### 📈 Visualizaciones Comerciales Interactivas")

    g_col1, g_col2 = st.columns(2)

    with g_col1:
        # Gráfico 1: Evolución Diaria
        st.markdown("**1. Evolución de Ventas Diarias (S/)**")
        diario_df = pd.DataFrame(metricas["diario"])
        if not diario_df.empty and "fecha" in diario_df.columns and "total" in diario_df.columns:
            fig_dia = go.Figure()
            fig_dia.add_trace(go.Bar(x=diario_df["fecha"], y=diario_df["total"], name="Ventas (S/)", marker_color=AZUL))
            fig_dia.add_trace(go.Scatter(x=diario_df["fecha"], y=diario_df["total"], name="Tendencia", mode="lines+markers", line=dict(color=NARANJA, width=2)))
            fig_dia.update_layout(height=320, margin=dict(l=10, r=10, t=25, b=10), plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_dia, use_container_width=True, key="plotly_ventas_dia")
        else:
            st.info("Sin registros de ventas en el período seleccionado.")

    with g_col2:
        # Gráfico 2: Top Productos
        st.markdown("**2. Artículos Más Vendidos (Por Recaudación)**")
        top_df = pd.DataFrame(metricas["top_productos"][:8])
        if not top_df.empty and "descripcion" in top_df.columns:
            fig_top = go.Figure(go.Bar(
                x=top_df["ingresos"],
                y=top_df["descripcion"],
                orientation="h",
                marker_color=VERDE,
                text=[f"S/ {v:,.2f}" for v in top_df["ingresos"]],
                textposition="outside",
            ))
            fig_top.update_layout(height=320, margin=dict(l=10, r=10, t=25, b=10), plot_bgcolor="rgba(0,0,0,0)",
                                  yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig_top, use_container_width=True, key="plotly_top_prods")
        else:
            st.info("Sin detalle de productos vendidos en este período.")

    g_col3, g_col4 = st.columns(2)
    with g_col3:
        # Gráfico 3: Distribución por tipo de comprobante
        st.markdown("**3. Distribución por Tipo de Comprobante**")
        tipo_df = pd.DataFrame(metricas["por_tipo"])
        if not tipo_df.empty and "tipo_comprobante" in tipo_df.columns:
            fig_pie = go.Figure(go.Pie(
                labels=tipo_df["tipo_comprobante"],
                values=tipo_df["monto"],
                hole=0.45,
                marker=dict(colors=[AZUL, VERDE, NARANJA, "#7B1FA2"]),
            ))
            fig_pie.update_layout(height=300, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig_pie, use_container_width=True, key="plotly_tipos_comp")
        else:
            st.info("Sin comprobantes para graficar.")

    with g_col4:
        # Gráfico 4: Clientes Top
        st.markdown("**4. Principales Clientes (Por Monto de Compra)**")
        cli_df = pd.DataFrame(metricas["top_clientes"][:8])
        if not cli_df.empty and "cliente_nombre" in cli_df.columns:
            fig_cli = go.Figure(go.Bar(
                x=cli_df["cliente_nombre"],
                y=cli_df["total"],
                marker_color="#4527A0",
                text=[f"S/ {v:,.2f}" for v in cli_df["total"]],
                textposition="outside",
            ))
            fig_cli.update_layout(height=300, margin=dict(l=10, r=10, t=20, b=10), plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_cli, use_container_width=True, key="plotly_top_cli")
        else:
            st.info("Sin clientes registrados en el período.")

    st.divider()

    # 2. GENERACIÓN Y DESCARGA EN PDF
    st.markdown("#### 📥 Compilador y Descarga de Informes en PDF")
    st.caption("El Agente 2 estructura y exporta el informe completo en formato PDF con gráficos incrustados a color, membrete oficial, KPIs y recomendaciones.")

    pdf_col1, pdf_col2 = st.columns([1.5, 2.5])
    with pdf_col1:
        tipo_doc_pdf = st.radio(
            "Tipo de Informe a Generar",
            [
                "📊 Informe Ejecutivo de Ventas (Con Gráficos)",
                "📦 Informe de Inventario y Stock Crítico",
            ],
            key="pdf_tipo_radio"
        )

        nombre_archivo = (
            f"Informe_Ventas_Jhanegsol_{f_desde}_{f_hasta}.pdf"
            if "Ventas" in tipo_doc_pdf
            else f"Informe_Inventario_Jhanegsol_{ahora_pe.strftime('%Y%m%d')}.pdf"
        )

        generar_btn = st.button("📄 Generar y Compilar Informe en PDF", type="primary", use_container_width=True)

    with pdf_col2:
        if generar_btn or "pdf_buffer_generado" in st.session_state:
            if generar_btn:
                with st.spinner("El Agente 2 está compilando tablas y renderizando gráficos en PDF..."):
                    if "Ventas" in tipo_doc_pdf:
                        pdf_bytes = generar_pdf_informe_ventas(f_desde, f_hasta)
                    else:
                        pdf_bytes = generar_pdf_informe_inventario()
                    st.session_state.pdf_buffer_generado = pdf_bytes
                    st.session_state.pdf_nombre_archivo = nombre_archivo

            pdf_actual = st.session_state.get("pdf_buffer_generado")
            nombre_actual = st.session_state.get("pdf_nombre_archivo", "informe_jhanegsol.pdf")

            if pdf_actual:
                st.success(f"✅ ¡Informe en PDF generado exitosamente! ({len(pdf_actual):,} bytes)")
                st.download_button(
                    label="📥 Descargar Informe Completo en PDF",
                    data=pdf_actual,
                    file_name=nombre_actual,
                    mime="application/pdf",
                    use_container_width=True,
                )

                # Previsualización del PDF
                with st.expander("👁️ Ver Previsualización del Documento PDF", expanded=True):
                    mostrar_previsualizacion_pdf(pdf_actual, height=480)


# ─────────────────────────── PESTAÑA: AGENTE 3 (CONSULTOR Q&A) ───────────────────────────

def _tab_agente_qa() -> None:
    st.markdown("### 💬 Agente 3: Consultor Comercial Q&A")
    st.caption("Asistente comercial inteligente 24/7. Responde dudas sobre ventas, inventario, clientes, finanzas y conceptos de negocio.")

    if "agente_msgs" not in st.session_state:
        st.session_state.agente_msgs = [{
            "role": "assistant",
            "content": "¡Hola! 👋 Soy **Jhani**, tu consultor comercial inteligente. Puedo revisar tu stock, ventas, "
                       "clientes, márgenes y notificarte por correo. Elige una pregunta rápida o escríbeme directamente.",
            "usados": [],
        }]

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        estilo = st.selectbox("Estilo de respuesta", list(ESTILOS), key="agente_estilo_qa")
    with c2:
        hay_ia = ia_disponible()
        prov = proveedor_ia()
        nombres_prov = {"groq": "Groq", "openai": "OpenAI", "anthropic": "Claude"}
        label_ia = f"Usar IA ({nombres_prov.get(prov, 'Nube')})" if hay_ia else "Usar IA (Requiere API Key)"
        usar_ia = st.toggle(label_ia, value=hay_ia, disabled=not hay_ia,
                            help="Requiere GROQ_API_KEY, OPENAI_API_KEY o ANTHROPIC_API_KEY en Secrets o variables de entorno. "
                                 "Sin API key, funciona gratis en Modo Local inteligente.")
    with c3:
        st.write("")
        if st.button("🧹 Nueva charla", use_container_width=True):
            st.session_state.agente_msgs = [{
                "role": "assistant",
                "content": "¡Hola! 👋 Charla reiniciada. ¿Qué consulta o análisis comercial deseas realizar hoy?",
                "usados": [],
            }]
            st.rerun()

    st.markdown("**⚡ Preguntas y Acciones Rápidas**")
    pregunta_boton = None
    cols = st.columns(4)
    for i, (ico, texto) in enumerate(ACCESOS_RAPIDOS):
        if cols[i % 4].button(f"{ico} {texto}", key=f"qa_btn_{i}", use_container_width=True):
            pregunta_boton = texto

    st.divider()

    # Historial de mensajes
    for n, m in enumerate(st.session_state.agente_msgs):
        with st.chat_message(m["role"], avatar="🤖" if m["role"] == "assistant" else "🧑‍💼"):
            st.markdown(m["content"])
            if m.get("usados"):
                _mostrar_resultados(m["usados"], f"qa_hist_{n}")

    # Entrada de texto del chat
    pregunta = st.chat_input("Pregúntale al Agente 3… ej: ¿cuánto vendimos ayer?, ¿qué productos reponer?") or pregunta_boton
    if pregunta:
        st.session_state.agente_msgs.append({"role": "user", "content": pregunta, "usados": []})
        historial = [{"role": m["role"], "content": m["content"]} for m in st.session_state.agente_msgs
                     if not (m["role"] == "assistant" and m is st.session_state.agente_msgs[0])]
        with st.spinner("Jhani está analizando tus datos en tiempo real…"):
            texto, usados, _ = responder(historial, estilo, usar_ia)
        st.session_state.agente_msgs.append({"role": "assistant", "content": texto, "usados": usados})
        st.rerun()

    if len(st.session_state.agente_msgs) > 1:
        md = "\n\n".join(f"**{'Jhani' if m['role'] == 'assistant' else 'Usuario'}:** {m['content']}"
                         for m in st.session_state.agente_msgs)
        st.download_button("💾 Descargar conversación (.md)", md.encode("utf-8"),
                           file_name=f"charla_jhani_{datetime.now():%Y%m%d_%H%M}.md")


# ─────────────────────────── PESTAÑA: DIAGNÓSTICO & SIMULADOR ───────────────────────────

def _tab_diagnostico_simulador() -> None:
    t_diag, t_sim, t_apr = st.tabs(["🩺 Diagnóstico de Salud", "🎯 Simulador Comercial", "🎓 Glosario & Aprendizaje"])

    # 1. DIAGNÓSTICO
    with t_diag:
        df = cargar_productos()
        if df.empty:
            st.info("Registra productos en el catálogo para generar el diagnóstico.")
        else:
            n = len(df)
            pct_quiebre = (df["stock"] <= df["stock_minimo"]).mean()
            pct_perdida = (df["precio"] < df["costo"]).mean()
            margen_prom = df["margen_pct"].mean()
            quietos = productos_sin_movimiento(60)
            n_quietos = len(quietos.get("tabla") or [])
            pct_quietos = min(n_quietos / n, 1)

            componentes = {
                "Disponibilidad": (1 - pct_quiebre) * 35,
                "Rentabilidad": max(0, min(margen_prom / 30, 1)) * 25,
                "Rotación": (1 - pct_quietos) * 25,
                "Precios sanos": (1 - pct_perdida) * 15,
            }
            puntaje = round(sum(componentes.values()))
            color = "#2E7D32" if puntaje >= 75 else "#F9A825" if puntaje >= 50 else "#C62828"

            c1, c2 = st.columns([1, 1.3])
            with c1:
                fig = go.Figure(go.Indicator(
                    mode="gauge+number", value=puntaje, number={"suffix": "/100"},
                    title={"text": "Salud del negocio"},
                    gauge={"axis": {"range": [0, 100]}, "bar": {"color": color},
                           "steps": [{"range": [0, 50], "color": "#FFEBEE"}, {"range": [50, 75], "color": "#FFF8E1"},
                                     {"range": [75, 100], "color": "#E8F5E9"}]}))
                fig.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=10))
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                maximos = {"Disponibilidad": 35, "Rentabilidad": 25, "Rotación": 25, "Precios sanos": 15}
                fig2 = go.Figure(go.Bar(
                    y=list(componentes), x=[componentes[k] / maximos[k] * 100 for k in componentes],
                    orientation="h", marker_color=AZUL, text=[f"{componentes[k]:.0f}/{maximos[k]}" for k in componentes],
                    textposition="outside"))
                fig2.update_layout(title="Composición del Puntaje", height=260, xaxis=dict(range=[0, 115], ticksuffix="%"),
                                   margin=dict(l=10, r=10, t=45, b=10), plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig2, use_container_width=True)

            st.markdown("#### 🚦 Hallazgos y Acciones Recomendadas")
            hallazgos = []
            bajo = productos_bajo_stock()
            if bajo.get("tabla"):
                hallazgos.append(("🔴", "Stock crítico", bajo["resumen"], "Revisa el pedido sugerido abajo."))
            marg = analisis_margenes()
            if pct_perdida > 0:
                hallazgos.append(("🟠", "Precios bajo el costo", marg["resumen"], "Actualiza precios en el Catálogo."))
            if n_quietos:
                hallazgos.append(("🟡", "Stock inmovilizado", quietos["resumen"], "Arma promociones o combos."))
            if not hallazgos:
                hallazgos.append(("🟢", "Todo en orden", "No se detectaron alertas críticas.", "¡Excelente gestión!"))
            cols = st.columns(len(hallazgos))
            for col, (ico, tit, desc, accion) in zip(cols, hallazgos):
                col.markdown(f"<div class='tarjeta'><h4>{ico} {tit}</h4><p>{desc}</p>"
                             f"<p style='margin-top:6px'><b>👉 {accion}</b></p></div>", unsafe_allow_html=True)

            st.markdown("#### 🛒 Sugerencia de Reabastecimiento")
            a, b = st.columns(2)
            cobertura = a.slider("Días que deseo cubrir", 7, 90, 30, step=7)
            entrega = b.slider("Días que tarda el proveedor", 1, 30, 7)
            rep = sugerir_reposicion(cobertura, entrega)
            st.write(rep["resumen"])
            if rep.get("tabla"):
                df_rep = pd.DataFrame(rep["tabla"])
                st.dataframe(df_rep, use_container_width=True, hide_index=True)

    # 2. SIMULADOR
    with t_sim:
        df = cargar_productos()
        if df.empty:
            st.info("Registra productos para usar el simulador.")
        else:
            opciones = (df["codigo"] + " · " + df["descripcion"]).tolist()
            elegido = st.selectbox("Elige un producto para simular", opciones)
            p = df.iloc[opciones.index(elegido)]
            dem = float(_demanda_diaria(60).get(p["id"], 0))

            t1, t2 = st.tabs(["💲 ¿Y si cambio el precio?", "📦 ¿Cuándo debo pedir?"])
            with t1:
                c1, c2 = st.columns(2)
                nuevo_precio = c1.number_input("Precio de venta (S/)", min_value=0.0, value=float(p["precio"]), step=0.5)
                descuento = c2.slider("Descuento promocional (%)", 0, 50, 0)
                precio_final = nuevo_precio * (1 - descuento / 100)
                margen_actual = p["precio"] - p["costo"]
                margen_nuevo = precio_final - p["costo"]
                m1, m2, m3 = st.columns(3)
                m1.metric("Precio final", f"S/ {precio_final:,.2f}", f"{precio_final - p['precio']:+.2f}")
                m2.metric("Ganancia por unidad", f"S/ {margen_nuevo:,.2f}", f"{margen_nuevo - margen_actual:+.2f}")
                pct = (margen_nuevo / precio_final * 100) if precio_final else 0
                m3.metric("Margen %", f"{pct:.1f}%")
                if margen_nuevo <= 0:
                    st.error("🚫 Con este precio vendes a pérdida.")
                else:
                    st.success("✅ Margen positivo sobre el costo.")
            with t2:
                c1, c2, c3 = st.columns(3)
                demanda = c1.number_input("Ventas por día (unid.)", min_value=0.0, value=round(dem, 2), step=0.1)
                entrega = c2.number_input("Días de entrega proveedor", min_value=1, value=7)
                seguridad = c3.number_input("Stock de seguridad", min_value=0, value=int(p["stock_minimo"]))
                reorden = demanda * entrega + seguridad
                m1, m2 = st.columns(2)
                m1.metric("Stock actual", f"{int(p['stock'])} u.")
                m2.metric("Punto de reorden", f"{reorden:.0f} u.")

    # 3. APRENDIZAJE
    with t_apr:
        st.markdown("#### 📖 Glosario Comercial y Conceptos Clave")
        glosario = {
            "💰 Margen de ganancia": "Lo que queda de cada venta después de pagar el costo. Margen % = (Precio - Costo) / Precio.",
            "🧾 IGV (18%)": "Impuesto general a las ventas. Precio final = Valor Venta × 1.18.",
            "🔄 Rotación de inventario": "Frecuencia con que se renueva la mercadería en un período.",
            "🅰️ Análisis ABC (Pareto)": "Clasificación de productos: A (80% ingresos), B (15%) y C (5%).",
            "📦 Punto de reorden": "Nivel de stock mínimo que dispara un nuevo pedido al proveedor.",
        }
        for k, v in glosario.items():
            with st.expander(k):
                st.write(v)


# ─────────────────────────── VISTA PRINCIPAL ───────────────────────────

def render_views_agent() -> None:
    # Iniciar programador en segundo plano si aún no está corriendo
    iniciar_programador()

    render_header("Sistema Multi-Agente IA",
                  "3 Agentes Especializados: Notificaciones por Correo, Informes Gráficos en PDF y Consultor Comercial Q&A", "🤖")
    st.markdown(CSS, unsafe_allow_html=True)

    prov = proveedor_ia()
    nombres_prov = {"groq": "Groq", "openai": "OpenAI", "anthropic": "Claude"}
    modo_ia_str = (
        f"<span class='badge-status badge-activo'>● IA Activa ({nombres_prov.get(prov, 'Nube')})</span>"
        if ia_disponible()
        else "<span class='badge-status badge-info'>● Modo Local Inteligente (Gratis y Offline)</span>"
    )

    # Hero Banner Multi-Agente
    st.markdown(f"""
    <div class='agente-hub-header'>
      <div style='display:flex; justify-content:space-between; align-items:center;'>
        <div>
          <h3 style='margin:0; font-size:1.35rem; color:#fff;'>Centro de Control Multi-Agente IA • JHANEGSOL S.A.C.</h3>
          <p style='margin:4px 0 0 0; color:#E3F2FD; font-size:0.9rem;'>
            Gestión comercial autónoma e inteligente: correos automáticos a las 8am y 5pm, reportes gráficos en PDF y consultor en vivo.
          </p>
        </div>
        <div>{modo_ia_str}</div>
      </div>
      <div class='agente-grid'>
        <div class='agente-mini-card'>
          <h4>✉️ Agente 1: Notificador</h4>
          <p>Envía reportes por correo sobre las ventas a pedido y automático a las <b>8:00 AM</b> (ayer) y <b>5:00 PM</b> (hoy).</p>
        </div>
        <div class='agente-mini-card'>
          <h4>📊 Agente 2: Gráficos & PDF</h4>
          <p>Genera informes visuales interactivos y compila <b>reportes descargables en PDF</b> con gráficos a color.</p>
        </div>
        <div class='agente-mini-card'>
          <h4>💬 Agente 3: Consultor Q&A</h4>
          <p>Responde preguntas sobre ventas, productos, stock y clientes, con diagnóstico y simulador.</p>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Botón superior de refresco
    _, c_ref = st.columns([5, 1.2])
    if c_ref.button("🔄 Actualizar Datos", use_container_width=True):
        limpiar_cache()
        st.toast("Datos refrescados exitosamente desde Supabase.")

    # 4 PESTAÑAS PRINCIPALES
    tab1, tab2, tab3, tab4 = st.tabs([
        "✉️ Agente 1: Correos y Ventas (8am / 5pm)",
        "📊 Agente 2: Informes Gráficos y PDF",
        "💬 Agente 3: Consultor Comercial Q&A",
        "🩺 Diagnóstico y Simulador",
    ])

    with tab1:
        _tab_agente_email()

    with tab2:
        _tab_agente_graficos_pdf()

    with tab3:
        _tab_agente_qa()

    with tab4:
        _tab_diagnostico_simulador()
