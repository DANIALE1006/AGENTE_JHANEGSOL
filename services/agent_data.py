"""
Capa de datos del Agente Jhanegsol IA.
Solo LECTURA: el agente nunca inserta, actualiza ni borra registros.
"""
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from core.database import get_supabase_client

TIPOS_VENTA = ["BOLETA DE VENTA", "FACTURA", "TICKET DE VENTA"]


def _leer_tabla(tabla: str, columnas: str = "*", pagina: int = 1000) -> List[Dict[str, Any]]:
    """Lee una tabla completa paginando (Supabase devuelve máx. 1000 filas por consulta)."""
    client = get_supabase_client()
    filas: List[Dict[str, Any]] = []
    inicio = 0
    while True:
        try:
            res = client.table(tabla).select(columnas).range(inicio, inicio + pagina - 1).execute()
        except Exception as e:  # tabla inexistente, permisos, red...
            print(f"[agente] No se pudo leer '{tabla}': {e}")
            break
        lote = res.data or []
        filas.extend(lote)
        if len(lote) < pagina:
            break
        inicio += pagina
    return filas


def _num(df: pd.DataFrame, col: str, defecto: float = 0.0) -> None:
    if col not in df.columns:
        df[col] = defecto
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(defecto)


@st.cache_data(ttl=120, show_spinner=False)
def cargar_productos() -> pd.DataFrame:
    df = pd.DataFrame(_leer_tabla("productos"))
    if df.empty:
        return pd.DataFrame(columns=["id", "codigo", "descripcion", "marca", "costo", "precio",
                                     "stock", "stock_minimo", "proveedor"])
    for c in ["costo", "precio", "stock"]:
        _num(df, c)
    _num(df, "stock_minimo", 5)
    for c in ["codigo", "descripcion", "marca", "proveedor"]:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str)
    df["margen_unit"] = df["precio"] - df["costo"]
    df["margen_pct"] = (df["margen_unit"] / df["precio"].where(df["precio"] > 0)).fillna(0) * 100
    df["valor_costo"] = df["stock"] * df["costo"]
    df["valor_venta"] = df["stock"] * df["precio"]
    return df


@st.cache_data(ttl=120, show_spinner=False)
def cargar_comprobantes() -> pd.DataFrame:
    df = pd.DataFrame(_leer_tabla("comprobantes"))
    if df.empty:
        return pd.DataFrame(columns=["id", "tipo_comprobante", "serie_numero", "cliente_nombre",
                                     "cliente_documento", "subtotal", "igv", "total", "created_at"])
    for c in ["subtotal", "igv", "total"]:
        _num(df, c)
    df["created_at"] = pd.to_datetime(df.get("created_at"), errors="coerce", utc=True)
    df["fecha"] = df["created_at"].dt.tz_convert("America/Lima").dt.date
    return df


@st.cache_data(ttl=120, show_spinner=False)
def cargar_detalle_ventas() -> pd.DataFrame:
    """Detalle de ventas (boletas, facturas y tickets) unido a fecha y producto."""
    det = pd.DataFrame(_leer_tabla("detalle_comprobante",
                                   "comprobante_id, producto_id, cantidad, precio_unitario"))
    comp = cargar_comprobantes()
    prods = cargar_productos()
    if det.empty or comp.empty:
        return pd.DataFrame(columns=["producto_id", "cantidad", "precio_unitario", "importe",
                                     "fecha", "codigo", "descripcion", "cliente_nombre"])
    _num(det, "cantidad")
    _num(det, "precio_unitario")
    det["importe"] = det["cantidad"] * det["precio_unitario"]
    ventas = comp[comp["tipo_comprobante"].isin(TIPOS_VENTA)][
        ["id", "fecha", "tipo_comprobante", "cliente_nombre"]
    ].rename(columns={"id": "comprobante_id"})
    det = det.merge(ventas, on="comprobante_id", how="inner")
    det = det.merge(prods[["id", "codigo", "descripcion", "marca", "costo"]],
                    left_on="producto_id", right_on="id", how="left")
    det["codigo"] = det["codigo"].fillna("S/C")
    det["descripcion"] = det["descripcion"].fillna("Producto eliminado")
    return det


def limpiar_cache() -> None:
    cargar_productos.clear()
    cargar_comprobantes.clear()
    cargar_detalle_ventas.clear()
