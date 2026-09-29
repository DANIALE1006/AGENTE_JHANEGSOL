"""
Vista de Gestión y Directorio de Proveedores.
"""
import pandas as pd
import streamlit as st
from ui.components import render_header
from core.database import ejecutar_consulta

def render_views_suppliers() -> None:
    render_header(
        "Directorio y Registro de Proveedores",
        "Administración de proveedores para compras y abastecimiento de inventario",
        "🏢",
    )

    with st.expander("➕ Registrar Nuevo Proveedor", expanded=False):
        with st.form("form_proveedor", clear_on_submit=True):
            nombre = st.text_input("Nombre o Razón Social *", placeholder="Ej: DISTRIBUIDORA AUTOMOTRIZ S.A.C.")
            c1, c2 = st.columns(2)
            with c1:
                ruc = st.text_input("RUC o DNI", placeholder="Ej: 20555666777")
                telefono = st.text_input("Teléfono / Celular", placeholder="Ej: 987654321")
            with c2:
                email = st.text_input("Correo Electrónico", placeholder="contacto@proveedor.com")

            submit = st.form_submit_button("💾 Guardar Proveedor", type="primary")

            if submit:
                if not nombre.strip():
                    st.error("❌ El nombre o razón social del proveedor es obligatorio.")
                else:
                    data = {
                        "nombre": nombre.strip().upper(),
                        "ruc_dni": ruc.strip(),
                        "telefono": telefono.strip(),
                        "email": email.strip().lower(),
                    }
                    res = ejecutar_consulta("proveedores", consulta_type="insert", data=data)
                    if res and getattr(res, "data", None):
                        st.success(f"✅ Proveedor '{nombre.upper()}' registrado exitosamente.")
                        st.rerun()
                    else:
                        st.error("❌ Error al registrar el proveedor en la base de datos.")

    st.subheader("📋 Directorio de Proveedores")
    proveedores = ejecutar_consulta("proveedores", consulta_type="select", order_col="nombre", desc=False)

    if proveedores:
        df_prov = pd.DataFrame(proveedores)
        busq = st.text_input("🔍 Buscar proveedor por nombre, RUC o email:")
        if busq:
            df_prov = df_prov[df_prov.apply(lambda r: busq.lower() in str(r).lower(), axis=1)]
        
        cols = ["nombre", "ruc_dni", "telefono", "email"]
        cols_display = [c for c in cols if c in df_prov.columns]
        
        st.dataframe(
            df_prov[cols_display],
            use_container_width=True,
            hide_index=True,
            column_config={
                "nombre": st.column_config.TextColumn("Razón Social / Nombre", width="large"),
                "ruc_dni": st.column_config.TextColumn("RUC / DNI", width="medium"),
                "telefono": st.column_config.TextColumn("Teléfono", width="medium"),
                "email": st.column_config.TextColumn("Email", width="medium"),
            }
        )
    else:
        st.info("ℹ️ No hay proveedores registrados en el sistema.")
