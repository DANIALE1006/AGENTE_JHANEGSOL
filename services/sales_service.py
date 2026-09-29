"""
Servicio de ventas, facturación electrónica (POS) y correlativos.
"""
from typing import Any, Dict, List, Optional, Tuple
from core.config import PREFIJOS, IGV_RATE
from core.database import ejecutar_consulta, ajustar_stock_rpc
from core.pdf_service import generar_pdf_comprobante

def obtener_siguiente_correlativo(tipo_doc: str) -> str:
    """Calcula y sugiere el siguiente número de serie para el comprobante."""
    prefijo = PREFIJOS.get(tipo_doc, "B001")
    ult_comps = ejecutar_consulta(
        "comprobantes",
        consulta_type="select",
        data="serie_numero",
        like_col="serie_numero",
        like_val=f"{prefijo}-%",
    )
    siguiente_num = 1
    if ult_comps:
        numeros = []
        for c in ult_comps:
            serie = c.get("serie_numero", "")
            if "-" in serie:
                partes = serie.split("-")
                if len(partes) >= 2 and partes[1].isdigit():
                    numeros.append(int(partes[1]))
        if numeros:
            siguiente_num = max(numeros) + 1
    
    return f"{prefijo}-{siguiente_num:06d}"

def calcular_totales(items: List[Dict[str, Any]]) -> Tuple[float, float, float]:
    """Calcula subtotal (base gravada), IGV (18%) y total general."""
    total_gen = sum(float(item["cantidad"]) * float(item["precio_unitario"]) for item in items)
    subtotal = total_gen / (1.0 + IGV_RATE)
    igv = total_gen - subtotal
    return round(subtotal, 2), round(igv, 2), round(total_gen, 2)

def emitir_venta_segura(
    tipo_doc: str,
    serie_num: str,
    cliente_nom: str,
    cliente_doc: str,
    items: List[Dict[str, Any]],
) -> Tuple[bool, str, Optional[bytes]]:
    """
    Emite una venta asegurando:
    1. Existencia del comprobante (no duplicados).
    2. Validación de stock disponible en tiempo real.
    3. Inserción en 'comprobantes' y 'detalle_comprobante'.
    4. Sincronización exacta de stock: Respetando el trigger de base de datos
       para BOLETA/FACTURA y aplicando ajuste controlado para TICKET DE VENTA.
    """
    serie_clean = serie_num.strip().upper()
    if not items:
        return False, "El carrito de compras está vacío.", None
    
    # 1. Validar si ya existe el comprobante
    existente = ejecutar_consulta("comprobantes", eq_col="serie_numero", eq_val=serie_clean)
    if existente:
        return False, f"El número de comprobante '{serie_clean}' ya ha sido emitido previamente.", None
    
    # 2. Validación de stock disponible antes de escribir en DB
    for item in items:
        p_id = item["id"]
        cant_sol = int(item["cantidad"])
        res_prod = ejecutar_consulta("productos", eq_col="id", eq_val=p_id)
        if not res_prod:
            return False, f"Producto no encontrado (ID: {p_id}).", None
        
        prod = res_prod[0]
        stock_actual = int(prod.get("stock") or 0)
        desc = prod.get("descripcion", item.get("descripcion", "Producto"))
        if cant_sol > stock_actual:
            return False, f"Stock insuficiente para '{desc}'. Disponible: {stock_actual}, Solicitado: {cant_sol}.", None

    # 3. Calcular totales
    subtotal, igv, total_gen = calcular_totales(items)

    # 4. Insertar comprobante principal
    comp_data = {
        "tipo_comprobante": tipo_doc,
        "serie_numero": serie_clean,
        "cliente_nombre": cliente_nom.strip().upper(),
        "cliente_documento": cliente_doc.strip(),
        "subtotal": subtotal,
        "igv": igv,
        "total": total_gen,
    }
    
    res_comp = ejecutar_consulta("comprobantes", consulta_type="insert", data=comp_data)
    if not res_comp or not getattr(res_comp, "data", None):
        return False, "Error al registrar la cabecera del comprobante en la base de datos.", None
    
    comp_id = res_comp.data[0]["id"]

    # 5. Insertar detalle (la columna total es generada automáticamente por la BD)
    for item in items:
        cant_item = int(item["cantidad"])
        pu_item = float(item["precio_unitario"])
        
        det_data = {
            "comprobante_id": comp_id,
            "producto_id": item["id"],
            "cantidad": cant_item,
            "precio_unitario": pu_item,
        }
        res_det = ejecutar_consulta("detalle_comprobante", consulta_type="insert", data=det_data)
        if not res_det:
            return False, f"Error al registrar el detalle del producto {item.get('descripcion', '')}.", None
        
        # Sincronización de Stock:
        # Si el tipo es 'TICKET DE VENTA', el trigger de DB no actúa, por lo que aplicamos RPC.
        # Para 'BOLETA DE VENTA' y 'FACTURA', el trigger de DB ya descuenta automáticamente (evitando el doble descuento).
        if tipo_doc == "TICKET DE VENTA":
            ajustar_stock_rpc(item["id"], -cant_item)

    # 6. Generar PDF
    pdf_bytes = generar_pdf_comprobante(
        tipo_doc=tipo_doc,
        serie_num=serie_clean,
        cliente_nom=cliente_nom.strip().upper(),
        cliente_doc=cliente_doc.strip(),
        items=items,
        subtotal=subtotal,
        igv=igv,
        total_gen=total_gen,
    )

    return True, f"✅ {tipo_doc} {serie_clean} emitido correctamente.", pdf_bytes
