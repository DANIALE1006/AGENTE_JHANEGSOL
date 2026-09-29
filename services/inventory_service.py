"""
Servicio de gestión de inventario, productos y compras (ingresos).
"""
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from core.database import ejecutar_consulta, ajustar_stock_rpc, get_supabase_client


def obtener_catalogo_productos() -> List[Dict[str, Any]]:
    """Obtiene la lista completa de productos ordenados por código."""
    prods = ejecutar_consulta("productos", consulta_type="select", order_col="codigo", desc=False)
    return prods if prods else []


def crear_producto(
    codigo: str,
    descripcion: str,
    marca: str = "",
    costo: float = 0.0,
    precio: float = 0.0,
    stock: int = 0,
    stock_minimo: int = 5,
    proveedor: str = "",
) -> Tuple[bool, str]:
    """Registra un nuevo producto en la base de datos."""
    codigo_clean = codigo.strip().upper()
    desc_clean = descripcion.strip()
    
    if not codigo_clean or not desc_clean:
        return False, "El código y la descripción son obligatorios."
    
    # Validar duplicados de código
    existente = ejecutar_consulta("productos", eq_col="codigo", eq_val=codigo_clean)
    if existente:
        return False, f"El código '{codigo_clean}' ya está registrado con otro producto."
    
    data = {
        "codigo": codigo_clean,
        "descripcion": desc_clean,
        "marca": marca.strip().upper() if marca else "",
        "costo": round(float(costo), 2),
        "precio": round(float(precio), 2),
        "stock": int(stock),
        "stock_minimo": int(stock_minimo),
        "proveedor": proveedor.strip() if proveedor else "",
    }
    
    res = ejecutar_consulta("productos", consulta_type="insert", data=data)
    if res and getattr(res, "data", None):
        return True, "Producto registrado exitosamente."
    return False, "Error al insertar el producto en la base de datos."


def verificar_disponibilidad_stock(producto_id: str, cantidad_requerida: int) -> Tuple[bool, int, str]:
    """
    Verifica si hay stock suficiente para un producto.
    Retorna (disponible: bool, stock_actual: int, mensaje: str).
    """
    res = ejecutar_consulta("productos", eq_col="id", eq_val=producto_id)
    if not res:
        return False, 0, "Producto no encontrado."
    
    prod = res[0]
    stock_actual = int(prod.get("stock") or 0)
    desc = prod.get("descripcion", "")
    
    if stock_actual <= 0:
        return False, stock_actual, f"El producto '{desc}' no cuenta con stock disponible (Stock: 0)."
    if cantidad_requerida > stock_actual:
        return False, stock_actual, f"Stock insuficiente para '{desc}'. Disponible: {stock_actual}, Solicitado: {cantidad_requerida}."
    
    return True, stock_actual, "Stock disponible."


def registrar_ingreso_compra(
    producto_id: str,
    cantidad: int,
    nuevo_costo: float,
    proveedor_id: Optional[str] = None,
    nro_factura: str = "",
) -> Tuple[bool, str]:
    """
    Registra el ingreso individual de mercadería por compra.
    """
    if cantidad <= 0:
        return False, "La cantidad a ingresar debe ser mayor a cero."
    
    # 1. Actualizar costo
    update_res = ejecutar_consulta(
        "productos",
        consulta_type="update",
        data={"costo": round(float(nuevo_costo), 2)},
        eq_col="id",
        eq_val=producto_id,
    )
    if not update_res:
        return False, "Error al actualizar el costo del producto."
    
    # 2. Ajustar stock mediante RPC atómico
    nuevo_stock = ajustar_stock_rpc(producto_id, int(cantidad))
    if nuevo_stock is None:
        return False, "Error al actualizar el stock en almacén."
    
    return True, f"Ingreso registrado correctamente. Nuevo stock disponible: {nuevo_stock} unidades."


def registrar_ingreso_compra_lote(
    items: List[Dict[str, Any]],
    proveedor_id: Optional[str] = None,
    nro_factura: str = ""
) -> Tuple[bool, str]:
    """
    Registra el ingreso masivo/multiproducto de mercadería.
    
    Estructura esperada de cada elemento en 'items':
    [
        {
            "producto_id": "uuid-o-id",
            "cantidad": 10,
            "nuevo_costo": 25.50
        }, ...
    ]
    """
    if not items:
        return False, "La lista de productos para ingresar está vacía."

    items_procesados = 0
    errores = []

    for idx, item in enumerate(items, start=1):
        p_id = item.get("producto_id")
        cant = int(item.get("cantidad", 0))
        costo = float(item.get("nuevo_costo", 0.0))

        if not p_id or cant <= 0:
            errores.append(f"Fila {idx}: Datos de producto o cantidad inválidos.")
            continue

        # 1. Actualizar costo en la tabla de productos
        upd_res = ejecutar_consulta(
            "productos",
            consulta_type="update",
            data={"costo": round(costo, 2)},
            eq_col="id",
            eq_val=p_id
        )

        if not upd_res:
            errores.append(f"Fila {idx}: Error al actualizar el costo del producto ID {p_id}.")
            continue

        # 2. Sumar stock de forma atómica mediante RPC
        nuevo_stock = ajustar_stock_rpc(p_id, cant)
        if nuevo_stock is None:
            errores.append(f"Fila {idx}: Error al incrementar stock en RPC para el producto ID {p_id}.")
            continue

        items_procesados += 1

    if errores and items_procesados == 0:
        return False, f"No se pudo procesar ningún producto. Detalle: {'; '.join(errores)}"
    elif errores:
        return True, f"Ingreso parcial completado ({items_procesados}/{len(items)} items procesados). Hubo observaciones: {'; '.join(errores)}"

    return True, f"Se procesó exitosamente el ingreso de {items_procesados} productos al inventario."


def obtener_metricas_inventario() -> Dict[str, Any]:
    """Calcula métricas clave del inventario para el dashboard."""
    prods = obtener_catalogo_productos()
    if not prods:
        return {
            "total_items": 0,
            "total_unidades": 0,
            "valor_costo": 0.0,
            "valor_venta": 0.0,
            "items_quiebre": 0,
        }
    
    df = pd.DataFrame(prods)
    df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0)
    df["costo"] = pd.to_numeric(df["costo"], errors="coerce").fillna(0.0)
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce").fillna(0.0)
    df["stock_minimo"] = pd.to_numeric(df["stock_minimo"], errors="coerce").fillna(5)
    
    total_items = len(df)
    total_unidades = int(df["stock"].sum())
    valor_costo = float((df["stock"] * df["costo"]).sum())
    valor_venta = float((df["stock"] * df["precio"]).sum())
    items_quiebre = int((df["stock"] <= df["stock_minimo"]).sum())
    
    return {
        "total_items": total_items,
        "total_unidades": total_unidades,
        "valor_costo": valor_costo,
        "valor_venta": valor_venta,
        "items_quiebre": items_quiebre,
    }


def obtener_productos_quiebre_stock() -> list:
    """Devuelve los productos cuyo stock actual es menor o igual al mínimo."""
    prods = obtener_catalogo_productos()
    if not prods:
        return []
    df = pd.DataFrame(prods)
    df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0)
    df["stock_minimo"] = pd.to_numeric(df["stock_minimo"], errors="coerce").fillna(5)
    
    quiebres = df[df["stock"] <= df["stock_minimo"]]
    return quiebres.to_dict(orient="records")


def obtener_top_productos_vendidos(limit: int = 5) -> list:
    """Calcula los productos más vendidos sumando las cantidades de detalle_comprobante."""
    client = get_supabase_client()
    try:
        res = client.table("detalle_comprobante").select("producto_id, cantidad, productos(codigo, descripcion, marca)").execute()
        if not res.data:
            return []
        
        data = []
        for item in res.data:
            prod_info = item.get("productos") or {}
            data.append({
                "codigo": prod_info.get("codigo", "S/C"),
                "descripcion": prod_info.get("descripcion", "Producto Desconocido"),
                "marca": prod_info.get("marca", ""),
                "cantidad_vendida": int(item.get("cantidad", 0))
            })
            
        df = pd.DataFrame(data)
        top_df = df.groupby(["codigo", "descripcion", "marca"])["cantidad_vendida"].sum().reset_index()
        top_df = top_df.sort_values(by="cantidad_vendida", ascending=False).head(limit)
        return top_df.to_dict(orient="records")
    except Exception as e:
        print(f"Error calculando top ventas: {e}")
        return []


def obtener_sugerencia_proveedores() -> list:
    """Muestra la relación de productos con su proveedor sugerido y costo asignado."""
    prods = obtener_catalogo_productos()
    if not prods:
        return []
        
    df = pd.DataFrame(prods)
    cols = ["codigo", "descripcion", "costo", "precio", "proveedor"]
    cols_existentes = [c for c in cols if c in df.columns]
    return df[cols_existentes].to_dict(orient="records")
