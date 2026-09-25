"""
Módulo de acceso y conexión segura a Supabase.
"""
from typing import Any, Dict, List, Optional
import streamlit as st
from supabase import Client, create_client
from core.config import get_supabase_url, get_supabase_key

_supabase_client: Optional[Client] = None

def get_supabase_client() -> Client:
    """Retorna la instancia del cliente Supabase."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    
    url = get_supabase_url()
    key = get_supabase_key()
    try:
        _supabase_client = create_client(url, key)
        return _supabase_client
    except Exception as e:
        if hasattr(st, "error"):
            st.error(f"❌ Error crítico al conectar con Supabase: {e}")
        raise e

@st.cache_resource
def init_supabase() -> Client:
    """Inicialización singleton cacheada para la app de Streamlit."""
    return get_supabase_client()

def ejecutar_consulta(
    tabla: str,
    consulta_type: str = "select",
    data: Any = None,
    eq_col: Optional[str] = None,
    eq_val: Any = None,
    like_col: Optional[str] = None,
    like_val: Optional[str] = None,
    order_col: Optional[str] = None,
    desc: bool = False,
    limit: Optional[int] = None,
) -> Any:
    """Ejecuta consultas de manera segura contra la base de datos Supabase."""
    client = get_supabase_client()
    try:
        query = client.table(tabla)
        if consulta_type == "select":
            query = query.select("*" if not data else data)
            if eq_col and eq_val is not None:
                query = query.eq(eq_col, eq_val)
            if like_col and like_val is not None:
                query = query.like(like_col, like_val)
            if order_col:
                query = query.order(order_col, desc=desc)
            if limit:
                query = query.limit(limit)
            res = query.execute()
            return res.data
        elif consulta_type == "insert":
            return query.insert(data).execute()
        elif consulta_type == "update":
            return query.update(data).eq(eq_col, eq_val).execute()
        elif consulta_type == "delete":
            return query.delete().eq(eq_col, eq_val).execute()
    except Exception as e:
        if hasattr(st, "error"):
            st.error(f"⚠️ Error en base de datos (Tabla '{tabla}'): {e}")
        print(f"Error en consulta Supabase ({tabla}): {e}")
        return None

def ajustar_stock_rpc(producto_id: str, delta: int) -> Optional[int]:
    """
    Ajusta el stock de forma atómica mediante la función RPC 'ajustar_stock'.
    Uso exclusivo para operaciones manuales/compras (NO para ventas/notas con trigger).
    """
    client = get_supabase_client()
    try:
        res = client.rpc("ajustar_stock", {"p_id": producto_id, "p_delta": int(delta)}).execute()
        return res.data
    except Exception as e:
        if hasattr(st, "error"):
            st.error(f"⚠️ Error al ajustar stock del producto {producto_id}: {e}")
        print(f"Error RPC ajustar_stock: {e}")
        return None
