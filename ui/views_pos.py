"""
Vista de Punto de Venta (POS) - Emisión de Boletas, Facturas y Tickets.
"""
import pandas as pd
import streamlit as st
from ui.components import render_header
from core.database import ejecutar_consulta
from core.pdf_service import mostrar_previsualizacion_pdf
from services.sales_service import (
    obtener_siguiente_correlativo,
    calcular_totales,
    emitir_venta_segura,
)

def render_views_pos() -> None:
    render_header(
        "Punto de Venta (POS) y Facturación Directa",
        "Emisión electrónica de Boletas de Venta, Facturas y Tickets con control de inventario",
        "🧾",
    )

    # Inicializar estados de sesión para el POS
    if "carrito_ventas" not in st.session_state:
        st.session_state.carrito_ventas = []
    if "pdf_generado" not in st.session_state:
        st.session_state.pdf_generado = None
    if "num_ultimo_comp" not in st.session_state:
        st.session_state.num_ultimo_comp = ""
    if "procesando_emision" not in st.session_state:
        st.session_state.procesando_emision = False

    # 1. Selección de Tipo de Comprobante y Cliente
    col_doc, col_cli = st.columns(2)
    with col_doc:
        tipo_doc = st.selectbox("Tipo de Comprobante *", ["BOLETA DE VENTA", "FACTURA", "TICKET DE VENTA"])
        serie_sugerida = obtener_siguiente_correlativo(tipo_doc)
        serie_num = st.text_input("Serie y Número de Comprobante", value=serie_sugerida)

    with col_cli:
        clientes_db = ejecutar_consulta("clientes", consulta_type="select", order_col="nombre", desc=False)
        df_cli = pd.DataFrame(clientes_db) if clientes_db else pd.DataFrame()
        
        opcion_cli = st.radio("Tipo de Cliente", ["Cliente Varios (Genérico)", "Cliente Registrado"], horizontal=True)
        cliente_nom = "CLIENTE VARIOS"
        cliente_doc = "00000000"

        if opcion_cli == "Cliente Registrado" and not df_cli.empty:
            cliente_sel = st.selectbox("Seleccionar Cliente", df_cli["nombre"].tolist())
            row_c = df_cli[df_cli["nombre"] == cliente_sel].iloc[0]
            cliente_nom = row_c["nombre"]
            cliente_doc = row_c.get("ruc_dni", "00000000")
        elif opcion_cli == "Cliente Registrado" and df_cli.empty:
            st.info("ℹ️ No hay clientes registrados aún. Puedes registrarlos en el módulo 'Clientes'.")

    st.divider()

    # 2. Buscador y Agregador de Productos al Carrito
    st.subheader("🛒 Agregar Productos a la Venta")
    prods = ejecutar_consulta("productos", consulta_type="select", data="id, codigo, descripcion, precio, stock", order_col="codigo")

    if prods:
        dict_prods = {
            f"{p['codigo']} | {p['descripcion']} (Stock: {p.get('stock', 0)} | S/. {float(p.get('precio', 0)):.2f})": p
            for p in prods
        }
        
        cp1, cp2, cp3 = st.columns([3, 1, 1])
        with cp1:
            p_sel_key = st.selectbox("Buscar Producto por Código / Descripción", list(dict_prods.keys()))
        with cp2:
            cant_v = st.number_input("Cantidad", min_value=1, value=1, step=1, key="pos_input_cant")
        with cp3:
            st.write("")
            st.write("")
            btn_add = st.button("➕ Agregar", type="secondary", use_container_width=True)

        if btn_add:
            p_info = dict_prods[p_sel_key]
            stock_disp = int(p_info.get("stock") or 0)
            
            # Verificar si ya está en el carrito
            item_existente = next((x for x in st.session_state.carrito_ventas if x["id"] == p_info["id"]), None)
            cant_actual_en_carrito = item_existente["cantidad"] if item_existente else 0
            cant_total_deseada = cant_v + cant_actual_en_carrito

            if stock_disp <= 0:
                st.error(f"❌ El producto '{p_info['descripcion']}' no tiene stock disponible (Stock: 0).")
            elif cant_total_deseada > stock_disp:
                st.error(f"⚠️ La cantidad total solicitada ({cant_total_deseada}) supera el stock disponible ({stock_disp}).")
            else:
                if item_existente:
                    item_existente["cantidad"] = cant_total_deseada
                    item_existente["subtotal"] = round(cant_total_deseada * item_existente["precio_unitario"], 2)
                else:
                    st.session_state.carrito_ventas.append({
                        "id": p_info["id"],
                        "codigo": p_info["codigo"],
                        "descripcion": p_info["descripcion"],
                        "cantidad": cant_v,
                        "precio_unitario": float(p_info["precio"]),
                        "subtotal": round(cant_v * float(p_info["precio"]), 2),
                    })
                st.success(f"✅ Agregado al carrito: {p_info['descripcion']}")
                st.rerun()

    # 3. Detalle del Carrito de Ventas
    if st.session_state.carrito_ventas:
        st.write("")
        st.subheader("📋 Detalle del Carrito")

        for idx, item in enumerate(st.session_state.carrito_ventas):
            col_d1, col_d2, col_d3, col_d4, col_d5 = st.columns([3, 1, 1, 1, 0.5])
            col_d1.write(f"**{item['codigo']}** — {item['descripcion']}")
            nueva_cant = col_d2.number_input("Cant.", min_value=1, value=int(item["cantidad"]), key=f"pos_cant_{idx}_{item['id']}")
            col_d3.write(f"P.U: S/. {item['precio_unitario']:.2f}")

            if nueva_cant != item["cantidad"]:
                # Validar stock antes de actualizar
                res_p = ejecutar_consulta("productos", eq_col="id", eq_val=item["id"])
                stock_real = int(res_p[0]["stock"]) if res_p else 0
                if nueva_cant > stock_real:
                    st.error(f"⚠️ No hay suficiente stock para {nueva_cant} unidades (Disponible: {stock_real}).")
                else:
                    st.session_state.carrito_ventas[idx]["cantidad"] = nueva_cant
                    st.session_state.carrito_ventas[idx]["subtotal"] = round(nueva_cant * item["precio_unitario"], 2)
                    st.rerun()

            col_d4.write(f"**S/. {item['subtotal']:.2f}**")
            
            if col_d5.button("❌", key=f"btn_del_{idx}_{item['id']}", help="Eliminar ítem"):
                st.session_state.carrito_ventas.pop(idx)
                st.rerun()

        # Resumen Financiero
        subtotal, igv, total_gen = calcular_totales(st.session_state.carrito_ventas)
        st.divider()

        col_m1, col_m2, col_m3, col_vaciar = st.columns([1.5, 1.5, 1.5, 1.5])
        col_m1.metric("Op. Gravada (Subtotal)", f"S/. {subtotal:.2f}")
        col_m2.metric("IGV (18%)", f"S/. {igv:.2f}")
        col_m3.metric("TOTAL A COBRAR", f"S/. {total_gen:.2f}")
        with col_vaciar:
            st.write("")
            if st.button("🗑️ Vaciar Carrito", use_container_width=True):
                st.session_state.carrito_ventas = []
                st.session_state.pdf_generado = None
                st.rerun()

        st.write("")
        # Botón de Emisión Principal
        btn_emitir = st.button(
            f"🖨️ EMITIR {tipo_doc}",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.procesando_emision,
        )

        if btn_emitir:
            st.session_state.procesando_emision = True
            with st.spinner(f"Procesando emisión de {tipo_doc} {serie_num}..."):
                ok, msg, pdf_bytes = emitir_venta_segura(
                    tipo_doc=tipo_doc,
                    serie_num=serie_num,
                    cliente_nom=cliente_nom,
                    cliente_doc=cliente_doc,
                    items=st.session_state.carrito_ventas,
                )
                st.session_state.procesando_emision = False

                if ok:
                    st.session_state.pdf_generado = pdf_bytes
                    st.session_state.num_ultimo_comp = serie_num
                    st.session_state.carrito_ventas = []
                    st.success(msg)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)

    # 4. Descarga y Previsualización de Comprobante Emitido
    if st.session_state.pdf_generado:
        st.divider()
        st.markdown("### 🎉 Comprobante Emitido Exitosamente")
        st.download_button(
            label=f"📄 Descargar Comprobante PDF ({st.session_state.num_ultimo_comp}.pdf)",
            data=st.session_state.pdf_generado,
            file_name=f"{st.session_state.num_ultimo_comp}.pdf",
            mime="application/pdf",
            type="primary",
        )
        mostrar_previsualizacion_pdf(st.session_state.pdf_generado)
