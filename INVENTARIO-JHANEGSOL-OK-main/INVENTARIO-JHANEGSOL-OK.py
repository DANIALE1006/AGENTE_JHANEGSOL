"""
Sistema Comercial, Inventarios y Facturación - JHANEGSOL S.A.C.
Punto de Entrada Principal de la Aplicación Streamlit.
"""
import streamlit as st

# 1. Configuración de Página
st.set_page_config(
    page_title="Sistema Jhanegsol - Facturación e Inventarios",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. Inicialización de Conexión
from core.database import init_supabase
init_supabase()

# 3. Importación de Vistas
from ui.views_catalog import render_views_catalog
from ui.views_suppliers import render_views_suppliers
from ui.views_customers import render_views_customers
from ui.views_inbound import render_views_inbound
from ui.views_pos import render_views_pos
from ui.views_credit_notes import render_views_credit_notes
from ui.views_history import render_views_history
from ui.views_agent import render_views_agent

# 4. Barra Lateral y Navegación
with st.sidebar:
    st.image(
        "https://cdn-icons-png.flaticon.com/512/2897/2897785.png",
        width=70,
    )
    st.markdown("### **JHANEGSOL S.A.C.**")
    st.caption("RUC: 20600000001 • Huacho, Lima")
    st.divider()

    menu = st.radio(
        "Navegación Principal",
        [
            "📋 Catálogo de Productos",
            "🏢 Proveedores",
            "👥 Listado y Clientes",
            "📥 Ingresos (Compras)",
            "🧾 Punto de Venta (POS)",
            "📝 Notas de Crédito / Débito",
            "📑 Historial y Reimpresión",
            "🤖 Agente IA Jhani",
        ],
        index=0,
    )
    
    st.divider()
    st.markdown(
        "<div style='font-size:0.75rem; color:#94A3B8;'>Sistema v2.0 - Arquitectura Modular<br>© 2026 JHANEGSOL S.A.C.</div>",
        unsafe_allow_html=True,
    )

# 5. Enrutamiento de Vistas
if menu == "📋 Catálogo de Productos":
    render_views_catalog()
elif menu == "🏢 Proveedores":
    render_views_suppliers()
elif menu == "👥 Listado y Clientes":
    render_views_customers()
elif menu == "📥 Ingresos (Compras)":
    render_views_inbound()
elif menu == "🧾 Punto de Venta (POS)":
    render_views_pos()
elif menu == "📝 Notas de Crédito / Débito":
    render_views_credit_notes()
elif menu == "📑 Historial y Reimpresión":
    render_views_history()
elif menu == "🤖 Agente IA Jhani":
    render_views_agent()
