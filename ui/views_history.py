"""
Vista de Historial de Comprobantes Emitidos y Reimpresión de PDFs.
"""
import pandas as pd
import streamlit as st
from ui.components import render_header, render_metric_card
from core.database import ejecutar_consulta, get_supabase_client
from core.pdf_service import generar_pdf_comprobante, mostrar_previsualizacion_pdf

def render_views_history() -> None:
    render_header(
        "Historial de Comprobantes y Reimpresión de PDFs",
        "Consulta de ventas pasadas, auditoría de transacciones y descarga de comprobantes en PDF",
        "📑",
    )

    client = get_supabase_client()
    comprobantes = ejecutar_consulta("comprobantes", consulta_type="select", order_col="created_at", desc=True, limit=200)

    if not comprobantes:
        st.info("ℹ️ No hay comprobantes emitidos en el sistema.")
        return

    df_comp = pd.DataFrame(comprobantes)
    
    # Métricas de resumen
    total_docs = len(df_comp)
    total_ventas = df_comp[df_comp["tipo_comprobante"].isin(["BOLETA DE VENTA", "FACTURA", "TICKET DE VENTA"])]["total"].sum()
    total_notas = df_comp[df_comp["tipo_comprobante"] == "NOTA DE CRÉDITO"]["total"].sum()
    neto = total_ventas - total_notas

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card("Total Comprobantes", f"{total_docs:,}", "Emitidos en el sistema")
    with c2:
        render_metric_card("Ventas Brutas", f"S/. {total_ventas:,.2f}", "Boletas + Facturas + Tickets")
    with c3:
        render_metric_card("Notas de Crédito", f"S/. {total_notas:,.2f}", "Devoluciones acumuladas")
    with c4:
        render_metric_card("Ingreso Neto", f"S/. {neto:,.2f}", "Total neto percibido")

    st.write("")
    st.divider()

    # Filtros de Búsqueda
    c_f1, c_f2 = st.columns([2, 2])
    with c_f1:
        busqueda = st.text_input("🔍 Buscar por serie, cliente o DNI/RUC:", placeholder="Ej: B001-000043 o JUAN")
    with c_f2:
        tipo_filtro = st.selectbox("Filtrar por Tipo de Documento", ["Todos", "BOLETA DE VENTA", "FACTURA", "TICKET DE VENTA", "NOTA DE CRÉDITO", "NOTA DE DÉBITO"])

    df_filtered = df_comp.copy()
    if tipo_filtro != "Todos":
        df_filtered = df_filtered[df_filtered["tipo_comprobante"] == tipo_filtro]
    
    if busqueda:
        df_filtered = df_filtered[df_filtered.apply(lambda r: busqueda.lower() in str(r).lower(), axis=1)]

    # Mostrar Tabla Resumen
    cols_display = ["tipo_comprobante", "serie_numero", "cliente_nombre", "cliente_documento", "subtotal", "igv", "total", "created_at"]
    st.dataframe(
        df_filtered[cols_display],
        use_container_width=True,
        hide_index=True,
        column_config={
            "tipo_comprobante": st.column_config.TextColumn("Tipo"),
            "serie_numero": st.column_config.TextColumn("Serie - Número"),
            "cliente_nombre": st.column_config.TextColumn("Cliente"),
            "cliente_documento": st.column_config.TextColumn("Doc."),
            "subtotal": st.column_config.NumberColumn("Subtotal", format="S/. %.2f"),
            "igv": st.column_config.NumberColumn("IGV", format="S/. %.2f"),
            "total": st.column_config.NumberColumn("Total", format="S/. %.2f"),
            "created_at": st.column_config.DatetimeColumn("Fecha Emisión", format="DD/MM/YYYY HH:mm"),
        }
    )

    st.write("")
    st.subheader("🔍 Ver Detalle y Reimprimir Comprobante en PDF")
    
    lista_series = df_filtered["serie_numero"].tolist()
    if lista_series:
        serie_sel = st.selectbox("Seleccione el Comprobante a Visualizar / Descargar:", lista_series)
        doc_row = df_filtered[df_filtered["serie_numero"] == serie_sel].iloc[0]

        # Consultar ítems de detalle
        detalles_res = client.table("detalle_comprobante").select(
            "cantidad, precio_unitario, total, productos(codigo, descripcion)"
        ).eq("comprobante_id", doc_row["id"]).execute()

        items_doc = []
        if detalles_res.data:
            for it in detalles_res.data:
                prod_info = it.get("productos") or {}
                items_doc.append({
                    "codigo": prod_info.get("codigo", "S/C"),
                    "descripcion": prod_info.get("descripcion", "Producto"),
                    "cantidad": it["cantidad"],
                    "precio_unitario": it["precio_unitario"],
                    "subtotal": it["total"],
                })

        with st.expander(f"📄 Detalle de {doc_row['tipo_comprobante']} {doc_row['serie_numero']}", expanded=True):
            col_info1, col_info2, col_info3 = st.columns(3)
            col_info1.write(f"**Cliente:** {doc_row['cliente_nombre']}")
            col_info1.write(f"**Doc. Identidad:** {doc_row['cliente_documento']}")
            
            col_info2.write(f"**Subtotal:** S/. {float(doc_row.get('subtotal', 0)):.2f}")
            col_info2.write(f"**IGV (18%):** S/. {float(doc_row.get('igv', 0)):.2f}")
            col_info2.write(f"**TOTAL:** S/. {float(doc_row.get('total', 0)):.2f}")

            # Generar PDF bajo demanda para reimpresión
            fecha_fmt = ""
            if doc_row.get("created_at"):
                try:
                    fecha_fmt = pd.to_datetime(doc_row["created_at"]).strftime("%d/%m/%Y %H:%M")
                except Exception:
                    fecha_fmt = str(doc_row.get("created_at"))

            pdf_reimpresion = generar_pdf_comprobante(
                tipo_doc=doc_row["tipo_comprobante"],
                serie_num=doc_row["serie_numero"],
                cliente_nom=doc_row["cliente_nombre"],
                cliente_doc=doc_row.get("cliente_documento", "00000000"),
                items=items_doc,
                subtotal=float(doc_row.get("subtotal", 0)),
                igv=float(doc_row.get("igv", 0)),
                total_gen=float(doc_row.get("total", 0)),
                fecha_emision=fecha_fmt,
            )

            with col_info3:
                st.download_button(
                    label=f"📥 Descargar PDF ({doc_row['serie_numero']}.pdf)",
                    data=pdf_reimpresion,
                    file_name=f"{doc_row['serie_numero']}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )

            if items_doc:
                st.write("**Ítems incluidos:**")
                st.dataframe(pd.DataFrame(items_doc), use_container_width=True, hide_index=True)
            
            mostrar_previsualizacion_pdf(pdf_reimpresion, height=450)
