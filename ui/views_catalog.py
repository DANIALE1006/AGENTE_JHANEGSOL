"""
Vista del Catálogo de Productos e Inventario.
"""
import pandas as pd
import streamlit as st
from ui.components import render_header, render_metric_card
from services.inventory_service import (
    obtener_catalogo_productos,
    crear_producto,
    obtener_metricas_inventario,
    obtener_productos_quiebre_stock,
    obtener_top_productos_vendidos,
    obtener_sugerencia_proveedores,
)
from core.database import ejecutar_consulta

def render_views_catalog() -> None:
    render_header(
        "Catálogo de Productos e Inventario",
        "Control en tiempo real de existencias, precios, costos y alertas de stock",
        "📋",
    )

    # 1. Métricas de Inventario
    metrics = obtener_metricas_inventario()
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_metric_card("Total Ítems", f"{metrics['total_items']:,}", "Productos registrados")
    with c2:
        render_metric_card("Unidades en Stock", f"{metrics['total_unidades']:,}", "Existencias físicas")
    with c3:
        render_metric_card("Valorización Costo", f"S/. {metrics['valor_costo']:,.2f}", "Capital invertido")
    with c4:
        render_metric_card("Valorización Venta", f"S/. {metrics['valor_venta']:,.2f}", "Potencial de venta")
    with c5:
        render_metric_card("Stock Crítico", f"{metrics['items_quiebre']}", "En alerta o quiebre", alert=(metrics['items_quiebre'] > 0))

    st.write("")
    st.divider()

    # 2. Reportes y Métricas Analíticas
    st.subheader("📊 Reportes Analíticos de Inventario y Ventas")
    
    tab_quiebre, tab_top, tab_prov = st.tabs([
        "⚠️ Productos en Quiebre de Stock", 
        "🔥 Productos Más Vendidos", 
        "🏢 Proveedores por Producto"
    ])

    with tab_quiebre:
        quiebres = obtener_productos_quiebre_stock()
        if quiebres:
            st.error(f"Se encontraron **{len(quiebres)}** productos en nivel crítico o quiebre de stock.")
            df_q = pd.DataFrame(quiebres)
            cols_q = [c for c in ["codigo", "marca", "descripcion", "stock", "stock_minimo", "proveedor"] if c in df_q.columns]
            st.dataframe(
                df_q[cols_q],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "codigo": st.column_config.TextColumn("Código"),
                    "marca": st.column_config.TextColumn("Marca"),
                    "descripcion": st.column_config.TextColumn("Descripción"),
                    "stock": st.column_config.NumberColumn("Stock Actual"),
                    "stock_minimo": st.column_config.NumberColumn("Stock Mínimo"),
                    "proveedor": st.column_config.TextColumn("Proveedor Sugerido"),
                }
            )
        else:
            st.success("✅ Todos los productos cuentan con stock superior al umbral mínimo.")

    with tab_top:
        top_ventas = obtener_top_productos_vendidos(limit=10)
        if top_ventas:
            df_top = pd.DataFrame(top_ventas)
            st.markdown("**Top 10 Productos con Mayor Rotación:**")
            st.dataframe(
                df_top,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "codigo": st.column_config.TextColumn("Código"),
                    "descripcion": st.column_config.TextColumn("Descripción del Producto"),
                    "marca": st.column_config.TextColumn("Marca"),
                    "cantidad_vendida": st.column_config.NumberColumn("Total Unidades Vendidas"),
                }
            )
        else:
            st.info("ℹ️ Aún no hay registros de ventas suficientes para construir el ranking.")

    with tab_prov:
        provs_prod = obtener_sugerencia_proveedores()
        if provs_prod:
            df_p = pd.DataFrame(provs_prod)
            st.markdown("**Relación de Productos con su Proveedor Sugerido y Costos:**")
            st.dataframe(
                df_p,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "codigo": st.column_config.TextColumn("Código"),
                    "descripcion": st.column_config.TextColumn("Descripción"),
                    "costo": st.column_config.NumberColumn("Costo Unit. (S/.)", format="S/. %.2f"),
                    "precio": st.column_config.NumberColumn("P. Venta (S/.)", format="S/. %.2f"),
                    "proveedor": st.column_config.TextColumn("Proveedor Asignado"),
                }
            )

    st.divider()

    # 3. Formulario para Nuevo Producto
    with st.expander("➕ Registrar Nuevo Producto al Catálogo", expanded=False):
        proveedores = ejecutar_consulta("proveedores", consulta_type="select", data="nombre")
        nombres_prov = [p["nombre"] for p in proveedores] if proveedores else []

        with st.form("form_nuevo_producto", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                codigo = st.text_input("Código del Producto *", placeholder="Ej: PROD-051")
                marca = st.text_input("Marca", placeholder="Ej: CASTROL, MARVIL, GENÉRICO")
                descripcion = st.text_area("Descripción Detallada *", placeholder="Ej: Aceite para motor 20W-50 1 Galón")
            with col2:
                costo = st.number_input("Costo Unitario (S/.) *", min_value=0.0, format="%.2f", step=0.50)
                precio = st.number_input("Precio de Venta (S/.) *", min_value=0.0, format="%.2f", step=0.50)
                stock_ini = st.number_input("Stock Inicial", min_value=0, value=0, step=1)
                stock_min = st.number_input("Stock Mínimo (Alerta de Quiebre)", min_value=1, value=5, step=1)
                
                prov_sel = st.selectbox("Proveedor Sugerido", ["(Sin asignar)"] + nombres_prov)
                proveedor_val = "" if prov_sel == "(Sin asignar)" else prov_sel

            submit_btn = st.form_submit_button("💾 Guardar Producto", type="primary", use_container_width=True)

            if submit_btn:
                if not codigo or not descripcion:
                    st.error("❌ El código y la descripción son obligatorios.")
                else:
                    ok, msg = crear_producto(
                        codigo=codigo,
                        descripcion=descripcion,
                        marca=marca,
                        costo=costo,
                        precio=precio,
                        stock=stock_ini,
                        stock_minimo=stock_min,
                        proveedor=proveedor_val,
                    )
                    if ok:
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

    st.divider()

    # 4. Listado y Filtros Generales
    st.subheader("🔍 Listado General de Productos")
    productos = obtener_catalogo_productos()
    
    if not productos:
        st.info("ℹ️ No hay productos registrados en el catálogo. Usa el botón superior para agregar el primero.")
        return

    df_prod = pd.DataFrame(productos)
    
    col_busq, col_filtro = st.columns([3, 1])
    with col_busq:
        busqueda = st.text_input("Buscar por código, marca, descripción o proveedor:", placeholder="Escribe para buscar...")
    with col_filtro:
        filtro_stock = st.selectbox("Filtrar por Stock", ["Todos", "En Alerta / Quiebre", "Con Stock (>0)", "Sin Stock (=0)"])

    if busqueda:
        df_prod = df_prod[df_prod.apply(lambda r: busqueda.lower() in str(r).lower(), axis=1)]

    if filtro_stock == "En Alerta / Quiebre":
        df_prod = df_prod[df_prod["stock"] <= df_prod["stock_minimo"]]
    elif filtro_stock == "Con Stock (>0)":
        df_prod = df_prod[df_prod["stock"] > 0]
    elif filtro_stock == "Sin Stock (=0)":
        df_prod = df_prod[df_prod["stock"] == 0]

    cols_order = ["codigo", "marca", "descripcion", "stock", "stock_minimo", "precio", "costo", "proveedor"]
    cols_display = [c for c in cols_order if c in df_prod.columns]
    
    st.dataframe(
        df_prod[cols_display],
        use_container_width=True,
        hide_index=True,
        column_config={
            "codigo": st.column_config.TextColumn("Código", width="small"),
            "marca": st.column_config.TextColumn("Marca", width="small"),
            "descripcion": st.column_config.TextColumn("Descripción", width="large"),
            "stock": st.column_config.NumberColumn("Stock Actual", help="Unidades disponibles físicas en almacén"),
            "stock_minimo": st.column_config.NumberColumn("Stock Mín.", help="Umbral de alerta"),
            "precio": st.column_config.NumberColumn("P. Venta (S/.)", format="S/. %.2f"),
            "costo": st.column_config.NumberColumn("Costo (S/.)", format="S/. %.2f"),
            "proveedor": st.column_config.TextColumn("Proveedor", width="medium"),
        }
    )
