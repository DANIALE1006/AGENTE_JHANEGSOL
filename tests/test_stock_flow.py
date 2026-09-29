"""
Suite de pruebas automatizadas para verificación de flujos de inventario,
ventas, notas de crédito, control de saldos y cálculo de stock sin dobles descuentos.
"""
import uuid
from typing import Dict, Any
from core.database import ejecutar_consulta, get_supabase_client
from services.sales_service import emitir_venta_segura
from services.credit_notes_service import (
    obtener_detalles_comprobante_con_saldo,
    emitir_nota_segura,
)
from services.inventory_service import registrar_ingreso_compra

def run_tests():
    print("=" * 70)
    print("🚀 INICIANDO SUITE DE PRUEBAS DE INVENTARIO Y FACTURACIÓN")
    print("=" * 70)

    test_uid = uuid.uuid4().hex[:6].upper()
    test_prod_code = f"TEST-P-{test_uid}"
    
    client = get_supabase_client()
    created_comprobante_ids = []
    created_prod_ids = []

    try:
        # 1. Crear producto de prueba con Stock Inicial = 20
        print("\n--- PASO 1: Creación de Producto de Prueba ---")
        p_res = client.table("productos").insert({
            "codigo": test_prod_code,
            "descripcion": f"Producto Test {test_uid}",
            "marca": "TEST-BRAND",
            "costo": 10.0,
            "precio": 25.0,
            "stock": 20,
            "stock_minimo": 5,
        }).execute()

        prod_id = p_res.data[0]["id"]
        created_prod_ids.append(prod_id)
        print(f"✅ Producto creado: {test_prod_code} (ID: {prod_id}) con Stock Inicial = 20")

        # 2. Venta de 2 unidades con BOLETA DE VENTA
        print("\n--- PASO 2: Venta de 2 unidades con BOLETA DE VENTA ---")
        serie_boleta = f"TB01-{test_uid}"
        cart_boleta = [{
            "id": prod_id,
            "codigo": test_prod_code,
            "descripcion": f"Producto Test {test_uid}",
            "cantidad": 2,
            "precio_unitario": 25.0,
            "subtotal": 50.0,
        }]
        
        ok, msg, _ = emitir_venta_segura(
            tipo_doc="BOLETA DE VENTA",
            serie_num=serie_boleta,
            cliente_nom="CLIENTE TEST",
            cliente_doc="12345678",
            items=cart_boleta,
        )
        assert ok, f"Fallo al emitir boleta: {msg}"
        
        # Registrar ID para limpieza
        comp_b = client.table("comprobantes").select("id").eq("serie_numero", serie_boleta).execute()
        created_comprobante_ids.append(comp_b.data[0]["id"])

        stock_act = client.table("productos").select("stock").eq("id", prod_id).execute().data[0]["stock"]
        print(f"📊 Stock tras venta de 2 unidades con BOLETA: {stock_act}")
        assert stock_act == 18, f"❌ ERROR: El stock esperado era 18, pero se obtuvo {stock_act} (¡Posible doble descuento!)."
        print("✅ Verificación exitosa: El stock se descontó exactamente 1x (20 -> 18).")

        # 3. Venta de 3 unidades con FACTURA
        print("\n--- PASO 3: Venta de 3 unidades con FACTURA ---")
        serie_factura = f"TF01-{test_uid}"
        cart_factura = [{
            "id": prod_id,
            "codigo": test_prod_code,
            "descripcion": f"Producto Test {test_uid}",
            "cantidad": 3,
            "precio_unitario": 25.0,
            "subtotal": 75.0,
        }]
        
        ok, msg, _ = emitir_venta_segura(
            tipo_doc="FACTURA",
            serie_num=serie_factura,
            cliente_nom="EMPRESA TEST S.A.C.",
            cliente_doc="20123456789",
            items=cart_factura,
        )
        assert ok, f"Fallo al emitir factura: {msg}"

        comp_f = client.table("comprobantes").select("id").eq("serie_numero", serie_factura).execute()
        created_comprobante_ids.append(comp_f.data[0]["id"])

        stock_act = client.table("productos").select("stock").eq("id", prod_id).execute().data[0]["stock"]
        print(f"📊 Stock tras venta de 3 unidades con FACTURA: {stock_act}")
        assert stock_act == 15, f"❌ ERROR: El stock esperado era 15, pero se obtuvo {stock_act}."
        print("✅ Verificación exitosa: Factura descontó exactamente 1x (18 -> 15).")

        # 4. Venta de 1 unidad con TICKET DE VENTA
        print("\n--- PASO 4: Venta de 1 unidad con TICKET DE VENTA ---")
        serie_ticket = f"TT01-{test_uid}"
        cart_ticket = [{
            "id": prod_id,
            "codigo": test_prod_code,
            "descripcion": f"Producto Test {test_uid}",
            "cantidad": 1,
            "precio_unitario": 25.0,
            "subtotal": 25.0,
        }]
        
        ok, msg, _ = emitir_venta_segura(
            tipo_doc="TICKET DE VENTA",
            serie_num=serie_ticket,
            cliente_nom="CLIENTE TICKET",
            cliente_doc="00000000",
            items=cart_ticket,
        )
        assert ok, f"Fallo al emitir ticket: {msg}"

        comp_t = client.table("comprobantes").select("id").eq("serie_numero", serie_ticket).execute()
        created_comprobante_ids.append(comp_t.data[0]["id"])

        stock_act = client.table("productos").select("stock").eq("id", prod_id).execute().data[0]["stock"]
        print(f"📊 Stock tras venta de 1 unidad con TICKET: {stock_act}")
        assert stock_act == 14, f"❌ ERROR: El stock esperado era 14, pero se obtuvo {stock_act}."
        print("✅ Verificación exitosa: Ticket descontó exactamente 1x (15 -> 14).")

        # 5. Ingreso de Mercadería (Compra) de 10 unidades
        print("\n--- PASO 5: Ingreso por Compra de 10 unidades ---")
        ok_ing, msg_ing = registrar_ingreso_compra(
            producto_id=prod_id,
            cantidad=10,
            nuevo_costo=12.0,
            nro_factura="FAC-COMP-001",
        )
        assert ok_ing, f"Fallo al registrar ingreso: {msg_ing}"

        stock_act = client.table("productos").select("stock").eq("id", prod_id).execute().data[0]["stock"]
        print(f"📊 Stock tras ingreso de 10 unidades: {stock_act}")
        assert stock_act == 24, f"❌ ERROR: El stock esperado era 24, pero se obtuvo {stock_act}."
        print("✅ Verificación exitosa: Ingreso de compra sumó exactamente 10 unidades (14 -> 24).")

        # 6. Devolución de 1 unidad con NOTA DE CRÉDITO sobre la BOLETA (que compró 2)
        print("\n--- PASO 6: Devolución de 1 unidad con NOTA DE CRÉDITO ---")
        serie_nc1 = f"TNC1-{test_uid}"
        
        # Consultar saldo antes de la nota
        comp_info, items_saldo, _ = obtener_detalles_comprobante_con_saldo(serie_boleta)
        assert len(items_saldo) == 1
        assert items_saldo[0]["cantidad_disponible"] == 2

        items_nc1 = [{
            "id": prod_id,
            "producto_id": prod_id,
            "codigo": test_prod_code,
            "descripcion": f"Producto Test {test_uid}",
            "cantidad": 1,
            "cantidad_disponible": 2,
            "precio_unitario": 25.0,
            "subtotal": 25.0,
        }]

        ok_nc, msg_nc, _ = emitir_nota_segura(
            tipo_nota="NOTA DE CRÉDITO",
            serie_nota=serie_nc1,
            doc_referencia=serie_boleta,
            motivo_clave="03 - Devolución total",
            motivo_detalle="Devolución de 1 unidad por prueba",
            items_a_procesar=items_nc1,
            cliente_nom="CLIENTE TEST",
            cliente_doc="12345678",
        )
        assert ok_nc, f"Fallo al emitir NC: {msg_nc}"

        comp_nc1 = client.table("comprobantes").select("id").eq("serie_numero", serie_nc1).execute()
        created_comprobante_ids.append(comp_nc1.data[0]["id"])

        stock_act = client.table("productos").select("stock").eq("id", prod_id).execute().data[0]["stock"]
        print(f"📊 Stock tras devolución de 1 unidad con NC: {stock_act}")
        assert stock_act == 25, f"❌ ERROR: El stock esperado era 25, pero se obtuvo {stock_act}."
        print("✅ Verificación exitosa: Nota de crédito sumó exactamente 1 unidad física (24 -> 25).")

        # 7. Comprobación de saldo disponible restante en la Boleta (debe ser 1)
        print("\n--- PASO 7: Verificación de Saldo Disponible en Boleta ---")
        _, items_saldo_post, _ = obtener_detalles_comprobante_con_saldo(serie_boleta)
        assert items_saldo_post[0]["cantidad_original"] == 2
        assert items_saldo_post[0]["cantidad_ya_devuelta"] == 1
        assert items_saldo_post[0]["cantidad_disponible"] == 1
        print("✅ Verificación exitosa: El saldo disponible restante es exactamente 1 unidad.")

        # 8. Intento de sobre-devolución (intentar devolver 2 cuando solo queda 1 disponible)
        print("\n--- PASO 8: Bloqueo de Sobre-Devolución ---")
        serie_nc2 = f"TNC2-{test_uid}"
        items_nc_invalida = [{
            "id": prod_id,
            "producto_id": prod_id,
            "codigo": test_prod_code,
            "descripcion": f"Producto Test {test_uid}",
            "cantidad": 2,  # Intenta devolver 2
            "cantidad_disponible": 1,  # Solo hay 1 disponible
            "precio_unitario": 25.0,
            "subtotal": 50.0,
        }]

        ok_invalido, msg_invalido, _ = emitir_nota_segura(
            tipo_nota="NOTA DE CRÉDITO",
            serie_nota=serie_nc2,
            doc_referencia=serie_boleta,
            motivo_clave="03 - Devolución total",
            motivo_detalle="Intento de sobre-devolución",
            items_a_procesar=items_nc_invalida,
            cliente_nom="CLIENTE TEST",
            cliente_doc="12345678",
        )
        assert not ok_invalido, "❌ ERROR: El sistema debió rechazar la sobre-devolución."
        print(f"✅ Verificación exitosa: El sistema bloqueó la sobre-devolución con mensaje: '{msg_invalido}'")

        # 9. Nota de Crédito por '05 - Descuento global' (NO debe alterar stock físico)
        print("\n--- PASO 9: Nota de Crédito por Descuento Global (Sin retorno de stock) ---")
        serie_nc3 = f"TNC3-{test_uid}"
        items_nc_desc = [{
            "id": prod_id,
            "producto_id": prod_id,
            "codigo": test_prod_code,
            "descripcion": f"Producto Test {test_uid}",
            "cantidad": 1,
            "cantidad_disponible": 1,
            "precio_unitario": 25.0,
            "subtotal": 25.0,
        }]

        ok_desc, msg_desc, _ = emitir_nota_segura(
            tipo_nota="NOTA DE CRÉDITO",
            serie_nota=serie_nc3,
            doc_referencia=serie_boleta,
            motivo_clave="05 - Descuento global",
            motivo_detalle="Ajuste comercial sin devolución de producto",
            items_a_procesar=items_nc_desc,
            cliente_nom="CLIENTE TEST",
            cliente_doc="12345678",
        )
        assert ok_desc, f"Fallo al emitir NC de descuento: {msg_desc}"
        
        comp_nc3 = client.table("comprobantes").select("id").eq("serie_numero", serie_nc3).execute()
        created_comprobante_ids.append(comp_nc3.data[0]["id"])

        stock_act = client.table("productos").select("stock").eq("id", prod_id).execute().data[0]["stock"]
        print(f"📊 Stock tras NC por Descuento Global: {stock_act}")
        assert stock_act == 25, f"❌ ERROR: El stock no debió cambiar (esperado: 25, obtenido: {stock_act})."
        print("✅ Verificación exitosa: El motivo Descuento Global no alteró el stock físico (permanece en 25).")

        print("\n" + "=" * 70)
        print("🎉 ¡TODAS LAS PRUEBAS (9/9) PASARON CON ÉXITO Y SIN ERRORES!")
        print("=" * 70)

    finally:
        # Limpieza de registros creados en el test
        print("\n🧹 Limpiando registros temporales de prueba en la base de datos...")
        for cid in created_comprobante_ids:
            try:
                client.table("detalle_comprobante").delete().eq("comprobante_id", cid).execute()
                client.table("comprobantes").delete().eq("id", cid).execute()
            except Exception as e:
                print(f"Error limpiando comprobante {cid}: {e}")
        
        try:
            client.table("devoluciones").delete().like("numero_boleta", f"%{test_uid}%").execute()
        except Exception as e:
            print(f"Error limpiando devoluciones de prueba: {e}")

        for pid in created_prod_ids:
            try:
                client.table("productos").delete().eq("id", pid).execute()
            except Exception as e:
                print(f"Error limpiando producto {pid}: {e}")
        
        print("✅ Base de datos limpia.")

if __name__ == "__main__":
    run_tests()
