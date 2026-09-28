"""
Vista del Agente Jhanegsol IA: chat, diagnóstico, simulador y zona de aprendizaje.
"""
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services.agent_brain import ESTILOS, ia_disponible, proveedor_ia, responder
from services.agent_data import cargar_productos, limpiar_cache
from services.agent_tools import (analisis_margenes, productos_bajo_stock, productos_sin_movimiento,
                                  sugerir_reposicion, _demanda_diaria)
from ui.components import render_header

AZUL = "#0D47A1"

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
]

CSS = """
<style>
.agente-hero {background: linear-gradient(120deg,#0D47A1 0%,#1565C0 55%,#42A5F5 100%);
  border-radius:16px;padding:20px 24px;color:#fff;display:flex;gap:18px;align-items:center;margin-bottom:14px}
.agente-hero .avatar{font-size:2.6rem;background:rgba(255,255,255,.18);border-radius:50%;
  width:68px;height:68px;display:flex;align-items:center;justify-content:center}
.agente-hero h3{margin:0;color:#fff}.agente-hero p{margin:2px 0 0 0;color:#E3F2FD;font-size:.9rem}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.75rem;font-weight:600;margin-top:6px}
.badge-ia{background:#C8E6C9;color:#1B5E20}.badge-local{background:#FFF3E0;color:#E65100}
.tarjeta{border:1px solid #E2E8F0;border-radius:12px;padding:14px;background:#fff;height:100%}
.tarjeta h4{margin:0 0 4px 0;font-size:.95rem}.tarjeta p{margin:0;font-size:.85rem;color:#475569}
</style>
"""


# ─────────────────────────── utilidades visuales ───────────────────────────

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
                        mode="lines+markers", line=dict(color="#F57C00"))
        fig.update_layout(yaxis2=dict(overlaying="y", side="right", range=[0, 105], ticksuffix="%"))
        fig.add_hline(y=80, line_dash="dot", line_color="#F57C00", yref="y2")
    fig.update_layout(title=spec.get("titulo", ""), height=340, margin=dict(l=10, r=10, t=45, b=10),
                      plot_bgcolor="rgba(0,0,0,0)", showlegend=(tipo == "pareto"))
    st.plotly_chart(fig, width="stretch", key=f"graf_{clave}")


def _mostrar_resultados(usados: list, clave: str) -> None:
    for i, u in enumerate(usados):
        r = u["resultado"]
        with st.expander(f"🔧 Datos consultados: **{r.get('titulo', u['nombre'])}**", expanded=(i == 0)):
            if r.get("grafico"):
                _grafico(r["grafico"], f"{clave}_{i}")
            if r.get("tabla"):
                df = pd.DataFrame(r["tabla"])
                st.dataframe(df, width="stretch", hide_index=True, key=f"tab_{clave}_{i}")
                st.download_button("📥 Descargar CSV", df.to_csv(index=False).encode("utf-8"),
                                   file_name=f"{u['nombre']}.csv", mime="text/csv", key=f"dl_{clave}_{i}")
            st.caption(f"Herramienta: `{u['nombre'
