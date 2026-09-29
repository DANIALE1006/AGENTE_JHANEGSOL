"""
Vista de Base de Datos y Gestión de Clientes.
"""
import pandas as pd
import streamlit as st
from ui.components import render_header
from core.database import ejecutar_consulta

def render_views_customers() -> None:
    render_header(
        "Listado y Gestión de Clientes",
        "Directorio de clientes frecuentes para facturación rápida y emisión de comprobantes",
        "👥",
    )

    with st.expander("➕ Registrar Nuevo Cliente", expanded=False):
        with st.form("form_cliente", clear_on_submit=True):
            cli_nom = st.text_input("Nombre o Razón Social del Cliente *", placeholder="Ej: JUAN PEREZ o TRANSPORTES S.A.C.")
            c1, c2 = st.columns(2)
            with c1:
                cli_doc = st.text_input("DNI o RUC *", placeholder="Ej: 45678901 o 20123456789")
                cli_tel = st.text_input("Teléfono / Celular", placeholder="Ej: 998877665")
            with c2:
                cli_dir = st.text_input("Dirección Fiscal / Domicilio", placeholder="Ej: Av. 28 de Julio 123, Huacho")

            submit = st.form_submit_button("💾 Guardar Cliente", type="primary")

            if submit:
                if not cli_nom.strip() or not cli_doc.strip():
                    st.error("❌ El nombre y el documento (DNI/RUC) son obligatorios.")
                else:
                    data = {
                        "nombre": cli_nom.strip().upper(),
                        "ruc_dni": cli_doc.strip(),
                        "telefono": cli_tel.strip(),
                        "direccion": cli_dir.strip().upper(),
                    }
                    res = ejecutar_consulta("clientes", consulta_type="insert", data=data)
                    if res and getattr(res, "data", None):
                        st.success(f"✅ Cliente '{cli_nom.upper()}' registrado exitosamente.")
                        st.rerun()
                    else:
                        st.error("❌ Error al registrar el cliente en la base de datos.")

    st.subheader("📋 Directorio de Clientes")
    clientes = ejecutar_consulta("clientes", consulta_type="select", order_col="nombre", desc=False)

    if clientes:
        df_cli = pd.DataFrame(clientes)
        busq = st.text_input("🔍 Buscar cliente por nombre, DNI/RUC o dirección:")
        if busq:
            df_cli = df_cli[df_cli.apply(lambda r: busq.lower() in str(r).lower(), axis=1)]

        cols = ["nombre", "ruc_dni", "telefono", "direccion"]
        cols_display = [c for c in cols if c in df_cli.columns]

        st.dataframe(
            df_cli[cols_display],
            use_container_width=True,
            hide_index=True,
            column_config={
                "nombre": st.column_config.TextColumn("Cliente / Razón Social", width="large"),
                "ruc_dni": st.column_config.TextColumn("DNI / RUC", width="medium"),
                "telefono": st.column_config.TextColumn("Teléfono", width="medium"),
                "direccion": st.column_config.TextColumn("Dirección", width="large"),
            }
        )
    else:
        st.info("ℹ️ No hay clientes registrados en el sistema.")
