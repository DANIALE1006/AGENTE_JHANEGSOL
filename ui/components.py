"""
Componentes compartidos de interfaz para Streamlit.
"""
import streamlit as st

def render_header(titulo: str, subtitulo: str = "", icono: str = "📦") -> None:
    """Renderiza el encabezado estándar para cada vista."""
    st.markdown(
        f"""
        <div style="background: linear-gradient(90deg, #1E293B 0%, #334155 100%); padding: 18px 24px; border-radius: 10px; margin-bottom: 20px; color: white;">
            <h2 style="margin:0; font-size: 1.5rem; color: #F8FAFC;">{icono} {titulo}</h2>
            {f'<p style="margin: 4px 0 0 0; font-size: 0.9rem; color: #94A3B8;">{subtitulo}</p>' if subtitulo else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_metric_card(label: str, value: str, help_text: str = "", alert: bool = False) -> None:
    """Renderiza una tarjeta de métrica estilizada."""
    border_color = "#EF4444" if alert else "#E2E8F0"
    bg_color = "#FEF2F2" if alert else "#FFFFFF"
    text_color = "#991B1B" if alert else "#0F172A"
    st.markdown(
        f"""
        <div style="background-color: {bg_color}; border: 1px solid {border_color}; padding: 14px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            <div style="font-size: 0.8rem; color: #64748B; font-weight: 600; text-transform: uppercase;">{label}</div>
            <div style="font-size: 1.4rem; font-weight: 700; color: {text_color}; margin-top: 4px;">{value}</div>
            {f'<div style="font-size: 0.75rem; color: #94A3B8; margin-top: 2px;">{help_text}</div>' if help_text else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )
