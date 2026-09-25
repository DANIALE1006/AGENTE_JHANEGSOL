"""
Vista de Emisión de Notas de Crédito, Débito y Devoluciones.
"""
import streamlit as st
from ui.components import render_header
from core.config import MOTIVOS_NOTA_CREDITO, MOTIVOS_NOTA_DEBITO
from core.pdf_service import mostrar_previsualizacion_pdf
from services.credit_notes_service import (
    obtener_siguiente_correlativo_nota,
    obtener_detalles_comprobante_con_saldo,
    emitir_nota_segura,
)

def render_views_credit_notes() -> None:
    render_header(
        "Notas de Crédito y Débito (Devoluciones y Ajustes)",
        "Emisión electrónica conforme a SUNAT con control estricto de saldo devuelto y stock",
        "📝",
    )

    if "pdf_nota_generado" not in st.session_state:
        st.session_state.pdf_nota_generado = None
    if "num_ultima_nota" not in st.session_state:
        st.session_state.num_ultima_nota = ""
    if "procesando_nota" not in st.session_state:
        st.session_state.procesando_nota = False

    tipo_nota = st.radio("Seleccione el Tipo de Documento de Ajuste", ["NOTA DE CRÉDITO", "NOTA DE DÉBITO"], horizontal=True)

    c1, c2 = st.columns(2)
    with c1:
        serie_sugerida = obtener_siguiente_correlativo_nota(tipo_nota)
        serie_nota = st.text_input("Serie y Número de la Nota", value=serie_sugerida)
    with c2:
        doc_ref = st.text_input("Número del Comprobante Original Afectado *", placeholder="Ej: B001-000043 o F001-000002")

    # Selección de Motivo SUNAT
    st.write("")
    motivos_dict = MOTIVOS_NOTA_CREDITO if tipo_nota == "NOTA DE CRÉDITO" else MOTIVOS_NOTA_DEBITO
    opciones_motivo = list(motivos_dict.keys())
    
    col_mot1, col_mot2 = st.columns([2, 2])
    with col_mot1:
        motivo_sel = st.selectbox("Motivo SUNAT *", opciones_motivo)
        info_motivo = motivos_dict[motivo_sel]
        if tipo_nota == "NOTA DE CRÉDITO":
            if info_motivo.get("restituye_stock", True):
                st.info("📦 **Efecto en Almacén:** Este motivo **restituye físicamente** las unidades al stock.")
            else:
                st.warning("⚠️ **Efecto en Almacén:** Este motivo es solo contable / financiero (**no** suma stock físico).")
    with col_mot2:
        motivo_detalle = st.text_input("Sustento o Detalle del Motivo", placeholder="Ej: Cliente solicitó anulación por desistimiento")

    st.divider()

    # Búsqueda y Validación del Comprobante Origen
    if doc_ref.strip():
        comp_orig, items_saldo, msg_info = obtener_detalles_comprobante_con_saldo(doc_ref.strip())

        if not comp_orig:
            st.error(f"❌ {msg_info}")
            return

        st.success(f"📄 **Comprobante Encontrado:** {comp_orig['tipo_comprobante']} {comp_orig['serie_numero']} | **Cliente:** {comp_orig['cliente_nombre']} ({comp_orig.get('cliente_documento', 'S/D')}) | **Total Orig.:** S/. {float(comp_orig.get('total', 0)):.2f}")

        if not items_saldo:
            st.warning("⚠️ No se encontraron productos asociados a este comprobante.")
            return

        st.markdown("### 🔍 Seleccionar Productos y Cantidades para la Nota")
        st.caption("El sistema valida automáticamente que no devuelvas más unidades de las disponibles.")

        items_a_devolver = []
        
        for item in items_saldo:
            p_id = item["producto_id"]
            desc = item["descripcion"]
            cant_orig = item["cantidad_original"]
            cant_ya_dev = item["cantidad_ya_devuelta"]
            cant_disp = item["cantidad_disponible"]
            pu = item["precio_unitario"]

            col_chk, col_info_saldo, col_cant = st.columns([3, 2, 1.5])
            
            with col_chk:
                if cant_disp > 0:
                    incluir = st.checkbox(f"**{item['codigo']}** — {desc}", key=f"nc_chk_{p_id}")
                else:
                    st.write(f"🔒 ~~**{item['codigo']}** — {desc}~~")
                    incluir = False
            
            with col_info_saldo:
                if cant_disp == 0:
                    st.markdown("<span style='color: #EF4444; font-size: 0.85rem;'>⚠️ Totalmente devuelto (0 disp.)</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<span style='color: #059669; font-size: 0.85rem;'>Original: {cant_orig} | Ya devuelto: {cant_ya_dev} | **Disponible: {cant_disp}**</span>", unsafe_allow_html=True)

            with col_cant:
                if cant_disp > 0:
                    cant_a_procesar = st.number_input(
                        "Cant.",
                        min_value=1,
                        max_value=cant_disp,
                        value=cant_disp,
                        key=f"nc_cant_val_{p_id}",
                    )
                else:
                    st.write("-")
                    cant_a_procesar = 0

            if incluir and cant_disp > 0 and cant_a_procesar > 0:
                items_a_devolver.append({
                    "id": p_id,
                    "producto_id": p_id,
                    "codigo": item["codigo"],
                    "descripcion": desc,
                    "cantidad": cant_a_procesar,
                    "cantidad_disponible": cant_disp,
                    "precio_unitario": pu,
                    "subtotal": round(cant_a_procesar * pu, 2),
                })

        st.write("")
        if items_a_devolver:
            total_nota = sum(x["subtotal"] for x in items_a_devolver)
            st.markdown(f"#### 💰 Total de la {tipo_nota}: **S/. {total_nota:.2f}**")
        
        btn_emitir_nota = st.button(
            f"🖨️ EMITIR {tipo_nota}",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.procesando_nota or not items_a_devolver,
        )

        if btn_emitir_nota:
            st.session_state.procesando_nota = True
            with st.spinner(f"Emitiendo {tipo_nota} {serie_nota}..."):
                ok, msg, pdf_bytes = emitir_nota_segura(
                    tipo_nota=tipo_nota,
                    serie_nota=serie_nota,
                    doc_referencia=doc_ref,
                    motivo_clave=motivo_sel,
                    motivo_detalle=motivo_detalle,
                    items_a_procesar=items_a_devolver,
                    cliente_nom=comp_orig.get("cliente_nombre", "CLIENTE VARIOS"),
                    cliente_doc=comp_orig.get("cliente_documento", "00000000"),
                )
                st.session_state.procesando_nota = False

                if ok:
                    st.session_state.pdf_nota_generado = pdf_bytes
                    st.session_state.num_ultima_nota = serie_nota
                    st.success(msg)
                    st.balloons()
                    st.rerun()
                else:
                    st.error(msg)

    # 4. Descarga y Previsualización de la Nota Emitida
    if st.session_state.pdf_nota_generado:
        st.divider()
        st.markdown("### 🎉 Nota de Ajuste Emitida con Éxito")
        st.download_button(
            label=f"📄 Descargar Nota PDF ({st.session_state.num_ultima_nota}.pdf)",
            data=st.session_state.pdf_nota_generado,
            file_name=f"{st.session_state.num_ultima_nota}.pdf",
            mime="application/pdf",
            type="primary",
        )
        mostrar_previsualizacion_pdf(st.session_state.pdf_nota_generado)
