"""
Servicio de Notas de Crédito, Débito y Devoluciones con control de saldo.
"""
from typing import Any, Dict, List, Optional, Tuple
from core.config import PREFIJOS, MOTIVOS_NOTA_CREDITO, MOTIVOS_NOTA_DEBITO
from core.database import ejecutar_consulta, get_supabase_client, ajustar_stock_rpc
from core.pdf_service import generar_pdf_comprobante
from services.sales_service import calcular_totales

def obtener_siguiente_correlativo_nota(tipo_nota: str) -> str:
    """Calcula y sugiere el siguiente número de serie para la Nota de Crédito/Débito."""
    prefijo = PREFIJOS.get(tipo_nota, "NC01")
    ult_notas = ejecutar_consulta(
        "comprobantes",
        consulta_type="select",
        data="serie_numero",
        like_col="serie_numero",
        like_val=f"{prefijo}-%",
    )
    sig_num = 1
    if ult_notas:
        nums = []
        for n in ult_notas:
            s = n.get("serie_numero", "")
            if "-" in s:
                partes = s.split("-")
                if len(partes) >= 2 and partes[1].isdigit():
                    nums.append(int(partes[1]))
        if nums:
            sig_num = max(nums) + 1
    
    return f"{prefijo}-{sig_num:06d}"

def consultar_historial_devoluciones_doc(serie_doc_referencia: str) -> Dict[str, int]:
    """
    Retorna un diccionario {producto_id: cantidad_ya_devuelta}
    para todas las devoluciones/notas emitidas sobre ese comprobante.
    """
    client = get_supabase_client()
    devoluciones_previas: Dict[str, int] = {}
    try:
        res = client.table("devoluciones").select("producto_id, cantidad").like("numero_boleta", f"%Afecta: {serie_doc_referencia}%").execute()
        if res.data:
            for d in res.data:
                pid = d.get("producto_id")
                cant = int(d.get("cantidad") or 0)
                devoluciones_previas[pid] = devoluciones_previas.get(pid, 0) + cant
    except Exception as e:
        print(f"Error consultando historial de devoluciones previas: {e}")
    
    return devoluciones_previas

def obtener_detalles_comprobante_con_saldo(serie_doc_referencia: str) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], str]:
    """
    Obtiene los datos del comprobante original y sus ítems con el saldo
    disponible real para devolver (descontando notas de crédito previas).
    """
    serie_clean = serie_doc_referencia.strip().upper()
    comp_res = ejecutar_consulta("comprobantes", eq_col="serie_numero", eq_val=serie_clean)
    if not comp_res:
        return None, [], f"No se encontró ningún comprobante con la serie '{serie_clean}'."
    
    comp_info = comp_res[0]
    comp_id = comp_info["id"]

    client = get_supabase_client()
    detalles_res = client.table("detalle_comprobante").select(
        "producto_id, cantidad, precio_unitario, productos(codigo, descripcion)"
    ).eq("comprobante_id", comp_id).execute()

    if not detalles_res.data:
        return comp_info, [], "El comprobante encontrado no tiene ítems de detalle registrados."

    # Obtener lo que ya fue devuelto previamente en notas anteriores
    devuelto_por_prod = consultar_historial_devoluciones_doc(serie_clean)

    items_con_saldo = []
    for item in detalles_res.data:
        p_id = item["producto_id"]
        prod_data = item.get("productos") or {}
        codigo = prod_data.get("codigo", "S/C")
        descripcion = prod_data.get("descripcion", "Producto")
        cant_original = int(item["cantidad"])
        pu = float(item["precio_unitario"])

        cant_ya_devuelta = devuelto_por_prod.get(p_id, 0)
        cant_disponible = max(0, cant_original - cant_ya_devuelta)

        items_con_saldo.append({
            "producto_id": p_id,
            "codigo": codigo,
            "descripcion": descripcion,
            "cantidad_original": cant_original,
            "cantidad_ya_devuelta": cant_ya_devuelta,
            "cantidad_disponible": cant_disponible,
            "precio_unitario": pu,
        })

    return comp_info, items_con_saldo, "Comprobante cargado correctamente."

def emitir_nota_segura(
    tipo_nota: str,
    serie_nota: str,
    doc_referencia: str,
    motivo_clave: str,
    motivo_detalle: str,
    items_a_procesar: List[Dict[str, Any]],
    cliente_nom: str,
    cliente_doc: str,
) -> Tuple[bool, str, Optional[bytes]]:
    """
    Emite una Nota de Crédito o Débito con:
    1. Validación estricta de saldo disponible (evita devolver más de lo comprado).
    2. Manejo preciso de stock según el motivo SUNAT (restitución física vs ajuste contable).
    3. Registro en 'comprobantes', 'detalle_comprobante' y 'devoluciones'.
    """
    serie_nota_clean = serie_nota.strip().upper()
    doc_ref_clean = doc_referencia.strip().upper()

    if not items_a_procesar:
        return False, "Debe seleccionar al menos un producto con cantidad válida.", None

    # Validar duplicados
    existente = ejecutar_consulta("comprobantes", eq_col="serie_numero", eq_val=serie_nota_clean)
    if existente:
        return False, f"La nota '{serie_nota_clean}' ya existe en la base de datos.", None

    # Validar que ningún ítem exceda la cantidad disponible
    for item in items_a_procesar:
        cant_nota = int(item["cantidad"])
        cant_disp = int(item.get("cantidad_disponible", cant_nota))
        if cant_nota <= 0:
            return False, f"La cantidad para '{item['descripcion']}' debe ser mayor a 0.", None
        if cant_nota > cant_disp:
            return False, f"No puedes devolver {cant_nota} unidades de '{item['descripcion']}'. Saldo disponible restante: {cant_disp}.", None

    # Calcular totales
    subtotal, igv, total_gen = calcular_totales(items_a_procesar)

    # Insertar en comprobantes
    comp_data = {
        "tipo_comprobante": tipo_nota,
        "serie_numero": serie_nota_clean,
        "cliente_nombre": cliente_nom.strip().upper(),
        "cliente_documento": cliente_doc.strip(),
        "subtotal": subtotal,
        "igv": igv,
        "total": total_gen,
    }
    res_comp = ejecutar_consulta("comprobantes", consulta_type="insert", data=comp_data)
    if not res_comp or not getattr(res_comp, "data", None):
        return False, "Error al crear la cabecera de la nota.", None

    comp_id = res_comp.data[0]["id"]

    # Determinar si el motivo restituye stock
    config_motivo = MOTIVOS_NOTA_CREDITO.get(motivo_clave, {"restituye_stock": True})
    restituye_stock = config_motivo.get("restituye_stock", True) if tipo_nota == "NOTA DE CRÉDITO" else False

    motivo_completo = f"[{motivo_clave}] {motivo_detalle.strip()}" if motivo_detalle.strip() else motivo_clave

    for item in items_a_procesar:
        p_id = item["id"] if "id" in item else item["producto_id"]
        cant = int(item["cantidad"])
        pu = float(item["precio_unitario"])

        # 1. Insertar detalle comprobante (el trigger de DB en detalle_comprobante suma +cant)
        det_data = {
            "comprobante_id": comp_id,
            "producto_id": p_id,
            "cantidad": cant,
            "precio_unitario": pu,
        }
        res_det = ejecutar_consulta("detalle_comprobante", consulta_type="insert", data=det_data)
        if not res_det:
            return False, f"Error al insertar detalle de comprobante para producto {p_id}.", None

        # 2. Registrar en devoluciones y sincronizar stock:
        # En la BD:
        # - detalle_comprobante trigger: +cant
        # - devoluciones trigger: -cant
        # => Al insertar en ambos, el efecto neto de los triggers es 0.
        # Por lo tanto, si el motivo es físico (restituye_stock=True), aplicamos +cant para que suba exactamente 1x.
        # Si el motivo es contable (restituye_stock=False), no llamamos RPC y el efecto neto queda en 0.
        if tipo_nota == "NOTA DE CRÉDITO":
            reg_dev = {
                "numero_boleta": f"{serie_nota_clean} (Afecta: {doc_ref_clean})",
                "producto_id": p_id,
                "cantidad": cant,
                "precio": pu,
                "motivo_devolucion": motivo_completo,
            }
            ejecutar_consulta("devoluciones", consulta_type="insert", data=reg_dev)

            if restituye_stock:
                ajustar_stock_rpc(p_id, cant)

        elif tipo_nota == "NOTA DE DÉBITO":
            pass

    # Generar PDF
    pdf_bytes = generar_pdf_comprobante(
        tipo_doc=tipo_nota,
        serie_num=serie_nota_clean,
        cliente_nom=cliente_nom.strip().upper(),
        cliente_doc=cliente_doc.strip(),
        items=items_a_procesar,
        subtotal=subtotal,
        igv=igv,
        total_gen=total_gen,
        doc_referencia=doc_ref_clean,
        motivo=motivo_completo,
    )

    return True, f"✅ {tipo_nota} {serie_nota_clean} emitida exitosamente.", pdf_bytes
