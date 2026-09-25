"""
Vista de Registro de Ingresos de Mercadería (Compras / Abastecimiento) y Dashboard Estadístico Avanzado.
"""
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from ui.components import render_header
from core.database import ejecutar_consulta
from services.inventory_service import registrar_ingreso_compra_lote


def render_views_inbound() -> None:
    render_header(
        "Ingresos de Mercadería (Compras y Entradas)",
        "Registro de nuevas existencias y análisis gráfico de inventario e inversión",
        "📥",
    )

    # Cargar datos solicitando SOLO columnas existentes en tu BD
    prods = ejecutar_consulta(
        "productos",
        consulta_type="select",
        data="id, codigo, descripcion, stock, costo",
        order_col="codigo",
    )
    provs = ejecutar_consulta(
        "proveedores",
        consulta_type="select",
        data="id, nombre",
        order_col="nombre",
    )

    # Creación de Pestañas
    tab_operacion, tab_analytics = st.tabs(["📝 Registro de Ingresos", "📊 Dashboard & Analytics"])

    # ==========================================
    # PESTAÑA 1: REGISTRO DE INGRESOS (LOTE)
    # ==========================================
    with tab_operacion:
        if "inbound_cart" not in st.session_state:
            st.session_state.inbound_cart = []

        if not prods or not isinstance(prods, list):
            st.warning("⚠️ No hay productos registrados en el catálogo. Por favor registra productos primero.")
            return

        dict_prods = {
            f"{p['codigo']} - {p['descripcion']} (Stock actual: {p.get('stock', 0)})": p
            for p in prods
        }

        dict_provs = {pr["nombre"]: pr["id"] for pr in provs} if provs and isinstance(provs, list) else {}
        lista_provs = ["(Sin proveedor asignado)"] + list(dict_provs.keys())

        st.markdown("### 📄 Datos del Comprobante")
        col_prov, col_fact = st.columns(2)
        with col_prov:
            prov_sel = st.selectbox("Proveedor", lista_provs)
        with col_fact:
            nro_fact_compra = st.text_input("N° Factura / Guía de Compra", placeholder="Ej: F001-000452")

        st.markdown("---")

        st.markdown("### ➕ Agregar Productos al Lote")
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])

        with c1:
            prod_sel = st.selectbox("Producto a Ingresar *", list(dict_prods.keys()))
            prod_info = dict_prods[prod_sel]

        with c2:
            cant_ingreso = st.number_input("Cantidad *", min_value=1, value=1, step=1)

        with c3:
            costo_def = float(prod_info["costo"]) if prod_info.get("costo") is not None else 0.0
            nuevo_costo = st.number_input("Costo Unitario (S/.) *", min_value=0.0, value=costo_def, format="%.2f", step=0.50)

        with c4:
            st.write("")
            st.write("")
            if st.button("➕ Añadir", use_container_width=True, type="secondary"):
                p_id = prod_info["id"]
                existente = next((item for item in st.session_state.inbound_cart if item["producto_id"] == p_id), None)

                if existente:
                    existente["cantidad"] += cant_ingreso
                    existente["nuevo_costo"] = nuevo_costo
                    existente["subtotal"] = round(existente["cantidad"] * nuevo_costo, 2)
                else:
                    st.session_state.inbound_cart.append({
                        "producto_id": p_id,
                        "codigo": prod_info["codigo"],
                        "descripcion": prod_info["descripcion"],
                        "cantidad": cant_ingreso,
                        "nuevo_costo": nuevo_costo,
                        "subtotal": round(cant_ingreso * nuevo_costo, 2),
                    })
                st.rerun()

        if st.session_state.inbound_cart:
            st.markdown("### 📋 Detalle de la Compra a Procesar")
            df_cart = pd.DataFrame(st.session_state.inbound_cart)

            st.dataframe(
                df_cart[["codigo", "descripcion", "cantidad", "nuevo_costo", "subtotal"]],
                column_config={
                    "codigo": "Código",
                    "descripcion": "Descripción",
                    "cantidad": "Cant.",
                    "nuevo_costo": st.column_config.NumberColumn("Costo Unit. (S/.)", format="S/ %.2f"),
                    "subtotal": st.column_config.NumberColumn("Subtotal (S/.)", format="S/ %.2f"),
                },
                hide_index=True,
                use_container_width=True,
            )

            col_tot, col_del, col_send = st.columns([2, 1, 1])

            with col_tot:
                total_lote = sum(item["subtotal"] for item in st.session_state.inbound_cart)
                st.metric("Total Inversión Lote", f"S/ {total_lote:.2f}")

            with col_del:
                if st.button("🗑️ Vaciar Lote", use_container_width=True):
                    st.session_state.inbound_cart = []
                    st.rerun()

            with col_send:
                if st.button("📥 Guardar e Ingresar Stock", type="primary", use_container_width=True):
                    prov_id = dict_provs.get(prov_sel) if prov_sel in dict_provs else None

                    ok, msg = registrar_ingreso_compra_lote(
                        items=st.session_state.inbound_cart,
                        proveedor_id=prov_id,
                        nro_factura=nro_fact_compra,
                    )

                    if ok:
                        st.success(f"✅ {msg}")
                        st.session_state.inbound_cart = []
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
        else:
            st.info("💡 El lote de compra está vacío. Selecciona un producto y presiona 'Añadir'.")

    # ==========================================
    # PESTAÑA 2: DASHBOARD Y ANALÍTICA AVANZADA
    # ==========================================
    with tab_analytics:
        st.markdown("### 📈 Control Visual, KPIs e Indicadores de Inventario Avanzados")

        if not prods or not isinstance(prods, list):
            st.info("No hay datos de productos suficientes para mostrar el dashboard.")
            return

        # ------------------------------------------
        # FILTRO DE FECHAS (GLOBAL PARA DASHBOARD)
        # ------------------------------------------
        st.markdown("#### 📅 Filtro por Rango de Fechas")
        col_f1, col_f2, col_f3 = st.columns([2, 2, 2])

        fecha_fin_default = datetime.now().date()
        fecha_inicio_default = fecha_fin_default - timedelta(days=180)

        with col_f1:
            fecha_inicio = st.date_input("Fecha Inicio", value=fecha_inicio_default)
        with col_f2:
            fecha_fin = st.date_input("Fecha Fin", value=fecha_fin_default)

        # Cargar productos
        df_prods = pd.DataFrame(prods)
        df_prods["stock"] = pd.to_numeric(df_prods["stock"], errors="coerce").fillna(0)
        df_prods["costo"] = pd.to_numeric(df_prods["costo"], errors="coerce").fillna(0.0)
        df_prods["stock_minimo"] = 5
        df_prods["inversion_total"] = df_prods["stock"] * df_prods["costo"]

        # Cargar movimientos de inventario
        movs = ejecutar_consulta("movimientos_inventario", consulta_type="select")
        df_movs = pd.DataFrame()

        if movs and isinstance(movs, list):
            df_movs = pd.DataFrame(movs)
            if "fecha" in df_movs.columns:
                df_movs["fecha"] = pd.to_datetime(df_movs["fecha"])
                mask = (df_movs["fecha"].dt.date >= fecha_inicio) & (df_movs["fecha"].dt.date <= fecha_fin)
                df_movs = df_movs.loc[mask]

        with col_f3:
            st.write("")
            st.write("")
            # Opción para exportar reporte
            if not df_prods.empty:
                csv = df_prods.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Reporte CSV",
                    data=csv,
                    file_name=f'reporte_inventario_{fecha_inicio}_al_{fecha_fin}.csv',
                    mime='text/csv',
                    use_container_width=True
                )

        st.markdown("---")

        # ------------------------------------------
        # CÁLCULO DE KPIS E INDICADORES CLAVE
        # ------------------------------------------
        costo_inventario_promedio = df_prods["inversion_total"].sum()

        if not df_movs.empty and "tipo" in df_movs.columns:
            df_movs_kpi = df_movs.merge(
                df_prods[["id", "costo"]],
                left_on="producto_id",
                right_on="id",
                how="left",
            )
            df_movs_kpi["costo"] = df_movs_kpi["costo"].fillna(0.0)
            df_movs_kpi["monto"] = df_movs_kpi["cantidad"] * df_movs_kpi["costo"]

            # Costo total de ventas/salidas
            costo_ventas = df_movs_kpi[df_movs_kpi["tipo"] == "SALIDA"]["monto"].sum()

            # Productos con movimientos
            prods_con_movimiento = df_movs_kpi["producto_id"].unique()
            df_inmovilizados = df_prods[~df_prods["id"].isin(prods_con_movimiento)]
            monto_inmovilizado = df_inmovilizados["inversion_total"].sum()
            cant_inmovilizados = len(df_inmovilizados)
        else:
            costo_ventas = 0.0
            monto_inmovilizado = costo_inventario_promedio
            cant_inmovilizados = len(df_prods)
            df_inmovilizados = df_prods.copy()

        # Rotación de inventario
        rotacion_inventario = (costo_ventas / costo_inventario_promedio) if costo_inventario_promedio > 0 else 0.0

        # Días de permanencia (DII)
        dias_rango = max((fecha_fin - fecha_inicio).days, 1)
        dias_inventario = (dias_rango / rotacion_inventario) if rotacion_inventario > 0 else 999.0

        # Cobertura estimada en meses
        salidas_mensuales_prom = (costo_ventas / (dias_rango / 30.4)) if dias_rango > 0 else 0.0
        meses_cobertura = (costo_inventario_promedio / salidas_mensuales_prom) if salidas_mensuales_prom > 0 else 99.0

        # Tarjetas de Métricas (KPIs)
        st.markdown("#### 🎯 Indicadores Clave de Desempeño (KPIs)")
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

        with kpi1:
            st.metric("Valor Total Stock", f"S/ {costo_inventario_promedio:,.2f}", help="Capital invertido en inventario.")
        with kpi2:
            st.metric("Rotación de Stock", f"{rotacion_inventario:.2f} x", help="Veces que rotó el inventario.")
        with kpi3:
            st.metric("Días en Almacén", f"{dias_inventario:.0f} días" if dias_inventario < 999 else "N/D", help="Días promedio de permanencia.")
        with kpi4:
            st.metric("Stock Inmovilizado", f"S/ {monto_inmovilizado:,.2f}", delta=f"{cant_inmovilizados} sin rotar", delta_color="inverse")
        with kpi5:
            st.metric("Cobertura Est.", f"{meses_cobertura:.1f} meses" if meses_cobertura < 99 else "> 12 meses")

        st.markdown("---")

        # ------------------------------------------
        # 1. GRÁFICO COMPARATIVO EN MONTOS (INGRESOS VS SALIDAS S/.)
        # ------------------------------------------
        st.markdown("#### 💵 1. Ingresos vs. Salidas en Montos (S/.)")
        if not df_movs.empty and "tipo" in df_movs.columns:
            df_movs_monto = df_movs.merge(
                df_prods[["id", "costo"]], left_on="producto_id", right_on="id", how="left"
            )
            df_movs_monto["costo"] = df_movs_monto["costo"].fillna(0.0)
            df_movs_monto["monto"] = df_movs_monto["cantidad"] * df_movs_monto["costo"]
            df_movs_monto["mes_año"] = df_movs_monto["fecha"].dt.strftime("%Y-%m")

            df_resumen_montos = df_movs_monto.groupby(["mes_año", "tipo"])["monto"].sum().reset_index()

            fig_montos = px.bar(
                df_resumen_montos,
                x="mes_año", y="monto", color="tipo", barmode="group", text_auto=".2f",
                labels={"mes_año": "Período", "monto": "Monto Total (S/.)", "tipo": "Movimiento"},
                color_discrete_map={"INGRESO": "#2E7D32", "SALIDA": "#C62828"},
            )
            fig_montos.update_layout(xaxis_title="Mes", yaxis_title="Soles (S/.)")
            st.plotly_chart(fig_montos, use_container_width=True)
        else:
            st.info("💡 No hay registros de movimientos en el rango de fechas seleccionado.")

        st.markdown("---")

        col_c1, col_c2 = st.columns(2)

        # ------------------------------------------
        # 2. MAYOR INVERSIÓN EN STOCK
        # ------------------------------------------
        with col_c1:
            st.markdown("#### 💰 2. Mayor Inversión en Stock (Top Productos)")
            df_top_inversion = df_prods.sort_values(by="inversion_total", ascending=False).head(8)
            fig_top_inv = px.bar(
                df_top_inversion, x="inversion_total", y="descripcion", orientation="h", text_auto=".2f",
                labels={"inversion_total": "Inversión Total (S/.)", "descripcion": "Producto"},
                color="inversion_total", color_continuous_scale="Blues"
            )
            fig_top_inv.update_layout(yaxis={"categoryorder": "total ascending"}, showlegend=False, xaxis_title="Soles (S/.)", yaxis_title="")
            st.plotly_chart(fig_top_inv, use_container_width=True)

        # ------------------------------------------
        # 3. CLASIFICACIÓN ABC PARETO
        # ------------------------------------------
        with col_c2:
            st.markdown("#### 📊 3. Clasificación ABC del Inventario (Pareto)")
            df_abc = df_prods.sort_values(by="inversion_total", ascending=False).copy()
            df_abc["acumulado"] = df_abc["inversion_total"].cumsum()
            total_inv = df_abc["inversion_total"].sum()
            df_abc["pct_acumulado"] = (df_abc["acumulado"] / total_inv) * 100 if total_inv > 0 else 0

            def clasificar_abc(pct):
                if pct <= 80:
                    return "Categoría A (80% valor)"
                elif pct <= 95:
                    return "Categoría B (15% valor)"
                else:
                    return "Categoría C (5% valor)"

            df_abc["Categoria_ABC"] = df_abc["pct_acumulado"].apply(clasificar_abc)
            df_abc_summary = df_abc.groupby("Categoria_ABC")["inversion_total"].sum().reset_index()

            fig_abc = px.pie(
                df_abc_summary, values="inversion_total", names="Categoria_ABC",
                color_discrete_sequence=px.colors.qualitative.Set2, hole=0.4
            )
            fig_abc.update_traces(textinfo="percent+label")
            st.plotly_chart(fig_abc, use_container_width=True)

        st.markdown("---")

        col_d1, col_d2 = st.columns(2)

        # ------------------------------------------
        # 4. RANKING DE SALIDAS / VENTAS
        # ------------------------------------------
        with col_d1:
            st.markdown("#### 🏆 4. Ranking de Productos Más Vendidos / Retirados")
            if not df_movs.empty and "tipo" in df_movs.columns:
                df_salidas = df_movs[df_movs["tipo"] == "SALIDA"].merge(
                    df_prods[["id", "descripcion", "costo"]], left_on="producto_id", right_on="id", how="left"
                )
                df_salidas["monto"] = df_salidas["cantidad"] * df_salidas["costo"]
                df_ranking = df_salidas.groupby("descripcion").agg(
                    Unidades_Salidas=("cantidad", "sum"),
                    Total_Soles=("monto", "sum")
                ).reset_index().sort_values(by="Unidades_Salidas", ascending=False)

                st.dataframe(
                    df_ranking,
                    column_config={
                        "descripcion": "Producto",
                        "Unidades_Salidas": "Unidades Salidas",
                        "Total_Soles": st.column_config.NumberColumn("Total Salidas (S/.)", format="S/ %.2f")
                    },
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.info("Sin datos de salidas en este rango.")

        # ------------------------------------------
        # 5. DETALLE DE PRODUCTOS INMOVILIZADOS
        # ------------------------------------------
        with col_d2:
            st.markdown("#### 🧊 5. Detalle de Productos Inmovilizados (Sin Rotación)")
            if not df_inmovilizados.empty:
                df_inm_show = df_inmovilizados[["codigo", "descripcion", "stock", "inversion_total"]].sort_values(
                    by="inversion_total", ascending=False
                )
                st.dataframe(
                    df_inm_show,
                    column_config={
                        "codigo": "Código",
                        "descripcion": "Descripción",
                        "stock": "Stock Parado",
                        "inversion_total": st.column_config.NumberColumn("Capital Parado (S/.)", format="S/ %.2f")
                    },
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.success("🎉 ¡Excelente! Todos los productos han tenido rotación en este rango.")

        st.markdown("---")

        # ------------------------------------------
        # 6. TABLA DE ALERTA CON FORMATO CONDICIONAL
        # ------------------------------------------
        st.markdown("#### 🚨 6. Alerta de Stock Crítico y Control Total")
        st.caption("Se resaltan en rojo los productos con stock menor o igual al mínimo (5 unidades).")

        def resaltar_bajo_stock(row):
            if row["stock"] <= row["stock_minimo"]:
                return ["background-color: #ffcdd2; color: #b71c1c; font-weight: bold;"] * len(row)
            return [""] * len(row)

        df_alertas = df_prods[["codigo", "descripcion", "stock", "stock_minimo", "costo", "inversion_total"]]

        styler = df_alertas.style.apply(resaltar_bajo_stock, axis=1).format({
            "costo": "S/ {:.2f}",
            "inversion_total": "S/ {:.2f}",
        })

        st.dataframe(styler, use_container_width=True, hide_index=True)
