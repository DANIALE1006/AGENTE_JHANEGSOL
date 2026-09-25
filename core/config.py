"""
Configuración central y constantes del Sistema Jhanegsol.
"""
import os

DEFAULT_SUPABASE_URL = "https://oqafvzwwooxkohkdmatv.supabase.co"
DEFAULT_SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9xYWZ2end3b294a29oa2RtYXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgyNjc5MTcsImV4cCI6MjEwMzg0MzkxN30.t8XQWINbWs0x2FYs2heSCW8wsASLg39_xgYQ__tnUW8"

def get_supabase_url() -> str:
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "SUPABASE_URL" in st.secrets:
            return st.secrets["SUPABASE_URL"]
    except Exception:
        pass
    return os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL)

def get_supabase_key() -> str:
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "SUPABASE_KEY" in st.secrets:
            return st.secrets["SUPABASE_KEY"]
    except Exception:
        pass
    return os.getenv("SUPABASE_KEY", DEFAULT_SUPABASE_KEY)

# Información de la Empresa
EMPRESA_NOMBRE = "JHANEGSOL S.A.C."
EMPRESA_RUC = "20600000001"
EMPRESA_DIRECCION = "Oficina Principal - Huacho, Lima - Perú"
EMPRESA_MENSAJE_PIE = "¡Gracias por su preferencia en JHANEGSOL S.A.C.!"

# Parámetros Tributarios y de Negocio
IGV_RATE = 0.18

# Prefijos de Comprobantes
PREFIJOS = {
    "BOLETA DE VENTA": "B001",
    "FACTURA": "F001",
    "TICKET DE VENTA": "T001",
    "NOTA DE CRÉDITO": "NC01",
    "NOTA DE DÉBITO": "ND01",
}

# Categorías de Motivo SUNAT para Notas de Crédito
MOTIVOS_NOTA_CREDITO = {
    "01 - Anulación de la operación": {"restituye_stock": True, "desc": "Anulación total de la venta con retorno de mercadería"},
    "02 - Anulación por error en el RUC": {"restituye_stock": False, "desc": "Corrección tributaria sin movimiento de mercadería"},
    "03 - Devolución total": {"restituye_stock": True, "desc": "Devolución total de los productos vendidos"},
    "04 - Devolución parcial": {"restituye_stock": True, "desc": "Devolución de parte de los productos vendidos"},
    "05 - Descuento global": {"restituye_stock": False, "desc": "Ajuste de precio / descuento sin retorno físico"},
    "06 - Devolución por ítem defectuoso": {"restituye_stock": True, "desc": "Retorno de mercadería defectuosa"},
}

MOTIVOS_NOTA_DEBITO = {
    "01 - Aumento en el valor": {"aumenta_costo": True, "desc": "Cobro de penalidad o intereses"},
    "02 - Penalidades / otros conceptos": {"aumenta_costo": True, "desc": "Penalidades u otros cobros adicionales"},
}
