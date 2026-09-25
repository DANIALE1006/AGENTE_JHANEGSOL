"""
Vista del Agente Jhanegsol IA: chat, diagnóstico, simulador y zona de aprendizaje.
"""
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services.agent_brain import ESTILOS, ia_disponible, responder
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
            st.caption(f"Herramienta: `{u['nombre']}` · parámetros: `{u['args'] or 'por defecto'}`")


# ─────────────────────────── pestaña: chat ───────────────────────────

def _tab_chat() -> None:
    if "agente_msgs" not in st.session_state:
        st.session_state.agente_msgs = [{
            "role": "assistant",
            "content": "¡Hola! 👋 Soy **Jhani**, tu asistente comercial. Puedo revisar tu stock, ventas, "
                       "clientes y márgenes, y explicarte cada indicador. Elige un acceso rápido o escríbeme.",
            "usados": [],
        }]

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        estilo = st.selectbox("Estilo de respuesta", list(ESTILOS), key="agente_estilo")
    with c2:
        hay_ia = ia_disponible()
        usar_ia = st.toggle("Usar IA (Claude)", value=hay_ia, disabled=not hay_ia,
                            help="Requiere ANTHROPIC_API_KEY en los Secrets de Streamlit. "
                                 "Sin ella, el agente funciona en modo local por palabras clave.")
    with c3:
        st.write("")
        if st.button("🧹 Nueva charla", width="stretch"):
            st.session_state.pop("agente_msgs", None)
            st.rerun()

    st.markdown("**⚡ Accesos rápidos**")
    pregunta_boton = None
    cols = st.columns(5)
    for i, (ico, texto) in enumerate(ACCESOS_RAPIDOS):
        if cols[i % 5].button(f"{ico} {texto}", key=f"qa_{i}", width="stretch"):
            pregunta_boton = texto

    st.divider()
    for n, m in enumerate(st.session_state.agente_msgs):
        with st.chat_message(m["role"], avatar="🤖" if m["role"] == "assistant" else "🧑‍💼"):
            st.markdown(m["content"])
            if m.get("usados"):
                _mostrar_resultados(m["usados"], f"h{n}")

    pregunta = st.chat_input("Pregúntale a Jhani… ej: ¿cuánto vendimos esta semana?") or pregunta_boton
    if pregunta:
        st.session_state.agente_msgs.append({"role": "user", "content": pregunta, "usados": []})
        historial = [{"role": m["role"], "content": m["content"]} for m in st.session_state.agente_msgs
                     if not (m["role"] == "assistant" and m is st.session_state.agente_msgs[0])]
        with st.spinner("Jhani está analizando tus datos…"):
            texto, usados, _ = responder(historial, estilo, usar_ia)
        st.session_state.agente_msgs.append({"role": "assistant", "content": texto, "usados": usados})
        st.rerun()

    if len(st.session_state.agente_msgs) > 1:
        md = "\n\n".join(f"**{'Jhani' if m['role'] == 'assistant' else 'Usuario'}:** {m['content']}"
                         for m in st.session_state.agente_msgs)
        st.download_button("💾 Descargar conversación (.md)", md.encode("utf-8"),
                           file_name=f"charla_jhani_{datetime.now():%Y%m%d_%H%M}.md")


# ─────────────────────────── pestaña: diagnóstico ───────────────────────────

def _tab_diagnostico() -> None:
    df = cargar_productos()
    if df.empty:
        st.info("Registra productos para obtener un diagnóstico.")
        return
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
        fig.update_layout(height=280, margin=dict(l=20, r=20, t=50, b=10))
        st.plotly_chart(fig, width="stretch")
    with c2:
        maximos = {"Disponibilidad": 35, "Rentabilidad": 25, "Rotación": 25, "Precios sanos": 15}
        fig2 = go.Figure(go.Bar(
            y=list(componentes), x=[componentes[k] / maximos[k] * 100 for k in componentes],
            orientation="h", marker_color=AZUL, text=[f"{componentes[k]:.0f}/{maximos[k]}" for k in componentes],
            textposition="outside"))
        fig2.update_layout(title="¿De dónde sale el puntaje?", height=280, xaxis=dict(range=[0, 115], ticksuffix="%"),
                           margin=dict(l=10, r=10, t=45, b=10), plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, width="stretch")

    st.markdown("#### 🚦 Hallazgos y acciones")
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
        hallazgos.append(("🟢", "Todo en orden", "No se detectaron alertas importantes.", "¡Sigue así!"))
    cols = st.columns(len(hallazgos))
    for col, (ico, tit, desc, accion) in zip(cols, hallazgos):
        col.markdown(f"<div class='tarjeta'><h4>{ico} {tit}</h4><p>{desc}</p>"
                     f"<p style='margin-top:6px'><b>👉 {accion}</b></p></div>", unsafe_allow_html=True)

    st.markdown("#### 🛒 Pedido sugerido")
    a, b = st.columns(2)
    cobertura = a.slider("Días que quiero cubrir", 7, 90, 30, step=7)
    entrega = b.slider("Días que tarda el proveedor", 1, 30, 7)
    rep = sugerir_reposicion(cobertura, entrega)
    st.write(rep["resumen"])
    if rep.get("tabla"):
        df_rep = pd.DataFrame(rep["tabla"])
        st.dataframe(df_rep, width="stretch", hide_index=True)
        st.download_button("📥 Descargar pedido (CSV)", df_rep.to_csv(index=False).encode("utf-8"),
                           file_name="pedido_sugerido.csv", mime="text/csv")


# ─────────────────────────── pestaña: simulador ───────────────────────────

def _tab_simulador() -> None:
    df = cargar_productos()
    if df.empty:
        st.info("Registra productos para usar el simulador.")
        return
    opciones = (df["codigo"] + " · " + df["descripcion"]).tolist()
    elegido = st.selectbox("Elige un producto", opciones)
    p = df.iloc[opciones.index(elegido)]
    dem = float(_demanda_diaria(60).get(p["id"], 0))

    t1, t2 = st.tabs(["💲 ¿Y si cambio el precio?", "📦 ¿Cuándo debo pedir?"])
    with t1:
        c1, c2 = st.columns(2)
        nuevo_precio = c1.number_input("Precio de venta (S/)", min_value=0.0,
                                       value=float(p["precio"]), step=0.5)
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
        elif margen_actual > 0 and margen_nuevo < margen_actual:
            extra = margen_actual / margen_nuevo
            st.info(f"📚 Para ganar lo mismo que hoy tendrías que vender **{extra:.1f} veces** más unidades "
                    f"(de {dem * 30:.0f} a {dem * 30 * extra:.0f} al mes aprox.). Un descuento solo conviene "
                    "si aumenta las ventas al menos en esa proporción.")
        else:
            st.success("✅ Esta configuración mejora tu ganancia por unidad.")
    with t2:
        c1, c2, c3 = st.columns(3)
        demanda = c1.number_input("Ventas por día (unid.)", min_value=0.0, value=round(dem, 2), step=0.1,
                                  help="Calculado con las ventas de los últimos 60 días. Puedes cambiarlo.")
        entrega = c2.number_input("Días de entrega del proveedor", min_value=1, value=7)
        seguridad = c3.number_input("Stock de seguridad", min_value=0, value=int(p["stock_minimo"]))
        reorden = demanda * entrega + seguridad
        dias_restantes = (p["stock"] - seguridad) / demanda if demanda > 0 else float("inf")
        m1, m2, m3 = st.columns(3)
        m1.metric("Stock actual", f"{int(p['stock'])} u.")
        m2.metric("Punto de reorden", f"{reorden:.0f} u.")
        m3.metric("Días hasta pedir", "∞" if dias_restantes == float("inf") else f"{max(dias_restantes - entrega, 0):.0f}")
        st.latex(r"\text{Punto de reorden} = \text{demanda diaria} \times \text{días de entrega} + \text{stock de seguridad}")
        st.caption(f"= {demanda:.2f} × {entrega} + {seguridad} = **{reorden:.0f} unidades**")
        if demanda > 0:
            dias = list(range(0, 61))
            stock_proy = [max(p["stock"] - demanda * d, 0) for d in dias]
            fig = go.Figure()
            fig.add_scatter(x=dias, y=stock_proy, name="Stock proyectado", line=dict(color=AZUL, width=3))
            fig.add_hline(y=reorden, line_dash="dash", line_color="#F57C00", annotation_text="Pedir aquí")
            fig.add_hline(y=seguridad, line_dash="dot", line_color="#C62828", annotation_text="Seguridad")
            fig.update_layout(title="Proyección de stock (60 días)", xaxis_title="Días", yaxis_title="Unidades",
                              height=320, margin=dict(l=10, r=10, t=45, b=10), plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Este producto no registra ventas en 60 días; ingresa una demanda estimada para simular.")


# ─────────────────────────── pestaña: aprende ───────────────────────────

GLOSARIO = {
    "💰 Margen de ganancia": "Lo que queda de cada venta después de pagar el costo. Si compras a S/ 60 y vendes a "
                            "S/ 100, el margen es S/ 40 (40%).",
    "🧾 IGV (18%)": "Impuesto que se cobra al cliente y se paga a SUNAT. Un precio de S/ 118 contiene "
                   "S/ 100 de valor de venta y S/ 18 de IGV.",
    "🔄 Rotación de inventario": "Cuántas veces se vende y repone el inventario en un periodo. Más rotación = el "
                                "dinero vuelve más rápido.",
    "🅰️ Análisis ABC": "Clasifica productos: A (≈80% de ingresos, pocos productos), B (15%) y C (5%, muchos "
                      "productos). Ayuda a decidir dónde poner la atención.",
    "📦 Punto de reorden": "Nivel de stock en el que hay que hacer el pedido para que llegue antes de agotarse.",
    "🛟 Stock de seguridad": "Unidades de reserva para cubrir imprevistos: retrasos del proveedor o picos de venta.",
    "🐢 Stock inmovilizado": "Mercadería que no se vende: ocupa espacio y es dinero detenido.",
    "🎫 Ticket promedio": "Ventas totales ÷ número de comprobantes. Indica cuánto gasta un cliente por compra.",
}

QUIZ = [
    ("Compras un producto a S/ 50 y lo vendes a S/ 80. ¿Cuál es su margen %?",
     ["37.5%", "60%", "30%"], "37.5%", "(80 − 50) ÷ 80 = 0.375 → 37.5%. El margen se calcula sobre el precio."),
    ("Vendes 4 unidades al día y el proveedor tarda 5 días. Con stock de seguridad de 10, ¿cuándo pides?",
     ["Al llegar a 30 unidades", "Al llegar a 20 unidades", "Al llegar a 10 unidades"], "Al llegar a 30 unidades",
     "4 × 5 + 10 = 30 unidades."),
    ("En un análisis ABC, ¿qué productos nunca deberían agotarse?",
     ["Clase A", "Clase B", "Clase C"], "Clase A", "Son pocos, pero generan la mayor parte de los ingresos."),
    ("Un precio de S/ 236 incluye IGV. ¿Cuánto es el IGV?",
     ["S/ 36", "S/ 42.48", "S/ 18"], "S/ 36", "236 ÷ 1.18 = 200 de valor de venta → IGV = 36."),
]


def _tab_aprende() -> None:
    st.markdown("#### 📖 Glosario comercial")
    cols = st.columns(2)
    for i, (t, d) in enumerate(GLOSARIO.items()):
        with cols[i % 2].expander(t):
            st.write(d)

    st.markdown("#### 🧠 Pon a prueba lo aprendido")
    respuestas = {}
    for i, (preg, ops, _, _) in enumerate(QUIZ):
        respuestas[i] = st.radio(f"**{i + 1}. {preg}**", ops, index=None, key=f"quiz_{i}")
    if st.button("✅ Revisar respuestas", type="primary"):
        aciertos = 0
        for i, (_, _, correcta, expl) in enumerate(QUIZ):
            if respuestas[i] == correcta:
                aciertos += 1
                st.success(f"{i + 1}. ¡Correcto! {expl}")
            else:
                st.error(f"{i + 1}. La respuesta era **{correcta}**. {expl}")
        st.progress(aciertos / len(QUIZ), text=f"Puntaje: {aciertos}/{len(QUIZ)}")
        if aciertos == len(QUIZ):
            st.balloons()


# ─────────────────────────── vista principal ───────────────────────────

def render_views_agent() -> None:
    render_header("Agente Inteligente Jhani",
                  "Tu analista comercial: pregunta, diagnostica, simula y aprende con tus datos reales", "🤖")
    st.markdown(CSS, unsafe_allow_html=True)
    modo = ("<span class='badge badge-ia'>● IA Claude activa</span>" if ia_disponible()
            else "<span class='badge badge-local'>● Modo local (sin API key)</span>")
    st.markdown(
        f"<div class='agente-hero'><div class='avatar'>🤖</div><div><h3>Hola, soy Jhani</h3>"
        f"<p>Consulto productos, ventas y clientes en Supabase en modo <b>solo lectura</b> y te explico cada "
        f"número.</p>{modo}</div></div>", unsafe_allow_html=True)

    _, c_ref = st.columns([5, 1])
    if c_ref.button("🔄 Actualizar datos", width="stretch"):
        limpiar_cache()
        st.toast("Datos actualizados desde Supabase")

    tab1, tab2, tab3, tab4 = st.tabs(["💬 Chat", "🩺 Diagnóstico", "🎯 Simulador", "🎓 Aprende"])
    with tab1:
        _tab_chat()
    with tab2:
        _tab_diagnostico()
    with tab3:
        _tab_simulador()
    with tab4:
        _tab_aprende()
