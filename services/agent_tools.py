"""
Herramientas (tools) del Agente Jhanegsol IA.

Cada herramienta devuelve un diccionario con:
  titulo   -> nombre corto del análisis
  resumen  -> texto con los hallazgos principales
  tabla    -> lista de registros para mostrar (opcional)
  grafico  -> especificación simple para Plotly (opcional)
  consejo  -> explicación didáctica del concepto usado (opcional)
"""
from __future__ import annotations
from datetime import date, timedelta
from typing import Any, Callable, Dict, List

import pandas as pd

from services.agent_data import cargar_comprobantes, cargar_detalle_ventas, cargar_productos, TIPOS_VENTA

Resultado = Dict[str, Any]


def _s(v: float) -> str:
    return f"S/ {v:,.2f}"


def _registros(df: pd.DataFrame, cols: List[str], n: int = 50) -> List[Dict[str, Any]]:
    cols = [c for c in cols if c in df.columns]
    return df[cols].head(n).round(2).to_dict(orient="records")


def _demanda_diaria(dias: int = 30) -> pd.Series:
    """Unidades vendidas por día (promedio) de cada producto en la ventana indicada."""
    det = cargar_detalle_ventas()
    if det.empty:
        return pd.Series(dtype=float)
    desde = date.today() - timedelta(days=dias)
    rec = det[det["fecha"] >= desde]
    return rec.groupby("producto_id")["cantidad"].sum() / max(dias, 1)


# ─────────────────────────── HERRAMIENTAS ───────────────────────────

def resumen_inventario() -> Resultado:
    df = cargar_productos()
    if df.empty:
        return {"titulo": "Resumen del inventario", "resumen": "No hay productos registrados."}
    quiebre = int((df["stock"] <= df["stock_minimo"]).sum())
    agotados = int((df["stock"] <= 0).sum())
    ganancia = df["valor_venta"].sum() - df["valor_costo"].sum()
    resumen = (
        f"Hay {len(df)} productos con {int(df['stock'].sum()):,} unidades en almacén. "
        f"Valor a costo: {_s(df['valor_costo'].sum())}; valor a precio de venta: {_s(df['valor_venta'].sum())} "
        f"(ganancia potencial {_s(ganancia)}). {quiebre} productos están en o bajo su stock mínimo y {agotados} agotados."
    )
    top = df.sort_values("valor_costo", ascending=False)
    return {
        "titulo": "Resumen del inventario",
        "resumen": resumen,
        "tabla": _registros(top, ["codigo", "descripcion", "stock", "costo", "precio", "valor_costo"], 15),
        "grafico": {"tipo": "bar", "x": "descripcion", "y": "valor_costo",
                    "titulo": "Productos con más capital invertido (S/)",
                    "datos": _registros(top, ["descripcion", "valor_costo"], 10)},
        "consejo": "El valor a costo es el dinero 'dormido' en el almacén. Si pocos productos concentran "
                   "mucho capital, conviene vigilar que roten rápido.",
    }


def productos_bajo_stock() -> Resultado:
    df = cargar_productos()
    bajo = df[df["stock"] <= df["stock_minimo"]].copy()
    if bajo.empty:
        return {"titulo": "Alertas de stock", "resumen": "✅ Ningún producto está por debajo de su stock mínimo."}
    bajo["faltante"] = (bajo["stock_minimo"] - bajo["stock"]).clip(lower=0)
    bajo["estado"] = bajo["stock"].apply(lambda s: "🔴 AGOTADO" if s <= 0 else "🟠 CRÍTICO")
    bajo = bajo.sort_values(["stock", "faltante"], ascending=[True, False])
    return {
        "titulo": "Alertas de stock",
        "resumen": f"{len(bajo)} productos requieren atención; {int((bajo['stock'] <= 0).sum())} ya están agotados.",
        "tabla": _registros(bajo, ["estado", "codigo", "descripcion", "stock", "stock_minimo", "faltante", "proveedor"]),
        "consejo": "El stock mínimo es el colchón de seguridad. Cuando se cruza, hay que pedir antes de "
                   "perder ventas por falta de producto (quiebre de stock).",
    }


def buscar_producto(texto: str) -> Resultado:
    df = cargar_productos()
    t = (texto or "").strip().lower()
    if not t:
        return {"titulo": "Búsqueda", "resumen": "Indica un código, nombre o marca para buscar."}
    mask = df[["codigo", "descripcion", "marca", "proveedor"]].apply(
        lambda col: col.str.lower().str.contains(t, regex=False)).any(axis=1)
    res = df[mask]
    if res.empty:
        return {"titulo": f"Búsqueda: {texto}", "resumen": f"No encontré productos que coincidan con '{texto}'."}
    return {
        "titulo": f"Búsqueda: {texto}",
        "resumen": f"Encontré {len(res)} producto(s) que coinciden con '{texto}'.",
        "tabla": _registros(res, ["codigo", "descripcion", "marca", "stock", "stock_minimo", "costo",
                                  "precio", "margen_pct", "proveedor"], 30),
    }


def resumen_ventas(dias: int = 30) -> Resultado:
    dias = int(dias or 30)
    comp = cargar_comprobantes()
    if comp.empty:
        return {"titulo": "Ventas", "resumen": "Aún no hay comprobantes emitidos."}
    desde = date.today() - timedelta(days=dias)
    per = comp[comp["fecha"] >= desde]
    ventas = per[per["tipo_comprobante"].isin(TIPOS_VENTA)]
    notas = per[per["tipo_comprobante"] == "NOTA DE CRÉDITO"]["total"].sum()
    bruto = ventas["total"].sum()
    n = len(ventas)
    ticket = bruto / n if n else 0
    diario = ventas.groupby("fecha")["total"].sum().reset_index()
    rango = pd.DataFrame({"fecha": pd.date_range(desde, date.today()).date})
    diario = rango.merge(diario, on="fecha", how="left").fillna(0)
    diario["fecha"] = diario["fecha"].astype(str)
    por_tipo = ventas.groupby("tipo_comprobante")["total"].agg(["count", "sum"]).reset_index()
    por_tipo.columns = ["tipo_comprobante", "cantidad", "monto"]
    return {
        "titulo": f"Ventas de los últimos {dias} días",
        "resumen": (f"{n} ventas por {_s(bruto)} (ticket promedio {_s(ticket)}). "
                    f"Notas de crédito: {_s(notas)}. Ingreso neto: {_s(bruto - notas)}. "
                    f"IGV incluido en ventas: {_s(ventas['igv'].sum())}."),
        "tabla": por_tipo.round(2).to_dict(orient="records"),
        "grafico": {"tipo": "line", "x": "fecha", "y": "total", "titulo": "Ventas diarias (S/)",
                    "datos": diario.round(2).to_dict(orient="records")},
        "consejo": "El ticket promedio = ventas ÷ número de comprobantes. Subirlo (combos, productos "
                   "complementarios) suele ser más barato que conseguir clientes nuevos.",
    }


def top_productos(limite: int = 10, dias: int = 90) -> Resultado:
    det = cargar_detalle_ventas()
    if det.empty:
        return {"titulo": "Más vendidos", "resumen": "Aún no hay ventas registradas."}
    desde = date.today() - timedelta(days=int(dias))
    rec = det[det["fecha"] >= desde]
    top = (rec.groupby(["codigo", "descripcion"])
              .agg(unidades=("cantidad", "sum"), ingresos=("importe", "sum"))
              .reset_index().sort_values("unidades", ascending=False).head(int(limite)))
    if top.empty:
        return {"titulo": "Más vendidos", "resumen": f"No hubo ventas en los últimos {dias} días."}
    lider = top.iloc[0]
    return {
        "titulo": f"Top {len(top)} productos ({dias} días)",
        "resumen": f"El más vendido es {lider['descripcion']} con {int(lider['unidades'])} unidades "
                   f"({_s(lider['ingresos'])}).",
        "tabla": top.round(2).to_dict(orient="records"),
        "grafico": {"tipo": "bar", "x": "descripcion", "y": "unidades", "titulo": "Unidades vendidas",
                    "datos": top[["descripcion", "unidades"]].to_dict(orient="records")},
    }


def analisis_abc(dias: int = 180) -> Resultado:
    det = cargar_detalle_ventas()
    if det.empty:
        return {"titulo": "Análisis ABC", "resumen": "Se necesitan ventas registradas para el análisis ABC."}
    desde = date.today() - timedelta(days=int(dias))
    g = (det[det["fecha"] >= desde].groupby(["codigo", "descripcion"])["importe"].sum()
         .reset_index().sort_values("importe", ascending=False))
    if g.empty or g["importe"].sum() <= 0:
        return {"titulo": "Análisis ABC", "resumen": f"No hubo ventas en los últimos {dias} días."}
    g["pct"] = g["importe"] / g["importe"].sum() * 100
    g["pct_acum"] = g["pct"].cumsum()
    g["clase"] = g["pct_acum"].apply(lambda p: "A" if p <= 80 else ("B" if p <= 95 else "C"))
    g.loc[g.index[0], "clase"] = "A"
    conteo = g["clase"].value_counts().to_dict()
    return {
        "titulo": "Análisis ABC (Pareto)",
        "resumen": (f"Clase A: {conteo.get('A', 0)} productos (≈80% de ingresos), "
                    f"B: {conteo.get('B', 0)}, C: {conteo.get('C', 0)}. "
                    "Los productos A nunca deberían faltar."),
        "tabla": g.round(2).to_dict(orient="records"),
        "grafico": {"tipo": "pareto", "x": "descripcion", "y": "importe", "y2": "pct_acum",
                    "titulo": "Curva de Pareto de ingresos",
                    "datos": g.head(25).round(2).to_dict(orient="records")},
        "consejo": "Principio de Pareto: pocos productos (clase A) generan la mayor parte del dinero. "
                   "A → control estricto; B → control normal; C → pedir poco y simple.",
    }


def sugerir_reposicion(dias_cobertura: int = 30, dias_entrega: int = 7) -> Resultado:
    df = cargar_productos().copy()
    if df.empty:
        return {"titulo": "Reposición", "resumen": "No hay productos."}
    dem = _demanda_diaria(60)
    df["demanda_dia"] = df["id"].map(dem).fillna(0)
    df["punto_reorden"] = (df["demanda_dia"] * int(dias_entrega) + df["stock_minimo"]).round()
    objetivo = df["demanda_dia"] * int(dias_cobertura) + df["stock_minimo"]
    df["pedir"] = (objetivo - df["stock"]).clip(lower=0).round()
    df["inversion"] = df["pedir"] * df["costo"]
    sug = df[(df["stock"] <= df["punto_reorden"]) & (df["pedir"] > 0)].sort_values("inversion", ascending=False)
    if sug.empty:
        return {"titulo": "Reposición", "resumen": "✅ No hace falta reponer nada por ahora."}
    return {
        "titulo": "Pedido de reposición sugerido",
        "resumen": (f"Sugiero reponer {len(sug)} productos ({int(sug['pedir'].sum())} unidades) con una "
                    f"inversión aproximada de {_s(sug['inversion'].sum())}, para cubrir {dias_cobertura} días "
                    f"considerando {dias_entrega} días de entrega del proveedor."),
        "tabla": _registros(sug, ["codigo", "descripcion", "proveedor", "stock", "demanda_dia",
                                  "punto_reorden", "pedir", "costo", "inversion"], 60),
        "consejo": "Punto de reorden = demanda diaria × días de entrega + stock de seguridad. "
                   "Cuando el stock baja de ese número, ya es hora de pedir.",
    }


def productos_sin_movimiento(dias: int = 60) -> Resultado:
    df = cargar_productos()
    det = cargar_detalle_ventas()
    desde = date.today() - timedelta(days=int(dias))
    vendidos = set(det[det["fecha"] >= desde]["producto_id"]) if not det.empty else set()
    quietos = df[(~df["id"].isin(vendidos)) & (df["stock"] > 0)].sort_values("valor_costo", ascending=False)
    if quietos.empty:
        return {"titulo": "Sin movimiento", "resumen": f"✅ Todo producto con stock se vendió en los últimos {dias} días."}
    return {
        "titulo": f"Productos sin ventas ({dias} días)",
        "resumen": f"{len(quietos)} productos con stock no se vendieron en {dias} días; "
                   f"tienen inmovilizados {_s(quietos['valor_costo'].sum())}.",
        "tabla": _registros(quietos, ["codigo", "descripcion", "stock", "costo", "valor_costo", "proveedor"]),
        "consejo": "El stock inmovilizado cuesta: ocupa espacio, se deteriora y es dinero que no circula. "
                   "Opciones: promociones, combos o devolverlo al proveedor.",
    }


def analisis_margenes() -> Resultado:
    df = cargar_productos()
    if df.empty:
        return {"titulo": "Márgenes", "resumen": "No hay productos."}
    perdida = df[df["precio"] < df["costo"]]
    bajos = df[(df["margen_pct"] < 15) & (df["precio"] >= df["costo"])]
    orden = df.sort_values("margen_pct")
    return {
        "titulo": "Análisis de márgenes",
        "resumen": (f"Margen promedio: {df['margen_pct'].mean():.1f}%. {len(perdida)} productos se venden por "
                    f"DEBAJO de su costo y {len(bajos)} tienen margen menor a 15%."),
        "tabla": _registros(orden, ["codigo", "descripcion", "costo", "precio", "margen_unit", "margen_pct"]),
        "grafico": {"tipo": "hist", "x": "margen_pct", "titulo": "Distribución de márgenes (%)",
                    "datos": _registros(df, ["margen_pct"], 5000)},
        "consejo": "Margen % = (precio − costo) ÷ precio × 100. Ojo: los precios incluyen IGV, así que la "
                   "ganancia real es algo menor que este margen bruto.",
    }


def top_clientes(limite: int = 10, dias: int = 180) -> Resultado:
    comp = cargar_comprobantes()
    if comp.empty:
        return {"titulo": "Clientes", "resumen": "No hay ventas registradas."}
    desde = date.today() - timedelta(days=int(dias))
    v = comp[(comp["tipo_comprobante"].isin(TIPOS_VENTA)) & (comp["fecha"] >= desde)]
    g = (v.groupby("cliente_nombre").agg(compras=("id", "count"), monto=("total", "sum"),
                                          ultima=("fecha", "max"))
          .reset_index().sort_values("monto", ascending=False).head(int(limite)))
    if g.empty:
        return {"titulo": "Clientes", "resumen": f"Sin ventas en {dias} días."}
    g["ultima"] = g["ultima"].astype(str)
    return {
        "titulo": f"Mejores clientes ({dias} días)",
        "resumen": f"El mejor cliente es {g.iloc[0]['cliente_nombre']} con {_s(g.iloc[0]['monto'])} "
                   f"en {int(g.iloc[0]['compras'])} compras.",
        "tabla": g.round(2).to_dict(orient="records"),
        "grafico": {"tipo": "bar", "x": "cliente_nombre", "y": "monto", "titulo": "Compras por cliente (S/)",
                    "datos": g[["cliente_nombre", "monto"]].round(2).to_dict(orient="records")},
    }


# ─────────────────────────── REGISTRO ───────────────────────────

HERRAMIENTAS: Dict[str, Callable[..., Resultado]] = {
    "resumen_inventario": resumen_inventario,
    "productos_bajo_stock": productos_bajo_stock,
    "buscar_producto": buscar_producto,
    "resumen_ventas": resumen_ventas,
    "top_productos": top_productos,
    "analisis_abc": analisis_abc,
    "sugerir_reposicion": sugerir_reposicion,
    "productos_sin_movimiento": productos_sin_movimiento,
    "analisis_margenes": analisis_margenes,
    "top_clientes": top_clientes,
}

_INT = {"type": "integer"}
TOOL_SPECS = [
    {"name": "resumen_inventario", "description": "Resumen general: productos, unidades, valor a costo y venta, alertas.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "productos_bajo_stock", "description": "Productos agotados o por debajo del stock mínimo.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "buscar_producto", "description": "Busca productos por código, nombre, marca o proveedor.",
     "input_schema": {"type": "object", "properties": {"texto": {"type": "string"}}, "required": ["texto"]}},
    {"name": "resumen_ventas", "description": "Ventas totales, ticket promedio, notas de crédito y ventas diarias de los últimos N días.",
     "input_schema": {"type": "object", "properties": {"dias": _INT}}},
    {"name": "top_productos", "description": "Productos más vendidos por unidades en los últimos N días.",
     "input_schema": {"type": "object", "properties": {"limite": _INT, "dias": _INT}}},
    {"name": "analisis_abc", "description": "Clasificación ABC (Pareto) de productos según ingresos.",
     "input_schema": {"type": "object", "properties": {"dias": _INT}}},
    {"name": "sugerir_reposicion", "description": "Calcula qué y cuánto pedir según demanda, días de cobertura y días de entrega.",
     "input_schema": {"type": "object", "properties": {"dias_cobertura": _INT, "dias_entrega": _INT}}},
    {"name": "productos_sin_movimiento", "description": "Productos con stock que no se vendieron en N días (stock inmovilizado).",
     "input_schema": {"type": "object", "properties": {"dias": _INT}}},
    {"name": "analisis_margenes", "description": "Márgenes de ganancia por producto; detecta precios bajo el costo.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "top_clientes", "description": "Clientes que más compran en los últimos N días.",
     "input_schema": {"type": "object", "properties": {"limite": _INT, "dias": _INT}}},
]


def ejecutar_herramienta(nombre: str, argumentos: Dict[str, Any] | None = None) -> Resultado:
    fn = HERRAMIENTAS.get(nombre)
    if fn is None:
        return {"titulo": "Error", "resumen": f"Herramienta desconocida: {nombre}"}
    try:
        return fn(**(argumentos or {}))
    except Exception as e:
        return {"titulo": "Error", "resumen": f"No se pudo ejecutar '{nombre}': {e}"}
