"""
Servicio de generación y previsualización de comprobantes en PDF.
"""
import io
import base64
from datetime import datetime
from typing import Any, Dict, List
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from core.config import EMPRESA_NOMBRE, EMPRESA_RUC, EMPRESA_DIRECCION, EMPRESA_MENSAJE_PIE

def generar_pdf_comprobante(
    tipo_doc: str,
    serie_num: str,
    cliente_nom: str,
    cliente_doc: str,
    items: List[Dict[str, Any]],
    subtotal: float,
    igv: float,
    total_gen: float,
    doc_referencia: str = "",
    motivo: str = "",
    fecha_emision: str = "",
) -> bytes:
    """Genera un archivo PDF profesional del comprobante."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )
    story = []
    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle(
        "Titulo",
        parent=styles["Heading1"],
        alignment=1,
        fontSize=16,
        leading=20,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1A202C")
    )
    subtitulo_style = ParagraphStyle(
        "SubTitulo",
        parent=styles["Normal"],
        alignment=1,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#4A5568")
    )
    comprobante_style = ParagraphStyle(
        "Comp",
        parent=styles["Heading2"],
        alignment=1,
        fontSize=13,
        leading=16,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0D47A1")
    )
    normal_style = styles["Normal"]
    derecha_style = ParagraphStyle("Derecha", parent=styles["Normal"], alignment=2)
    bold_derecha = ParagraphStyle("BoldDerecha", parent=styles["Normal"], alignment=2, fontName="Helvetica-Bold")

    # Encabezado Empresa
    story.append(Paragraph(EMPRESA_NOMBRE, titulo_style))
    story.append(Paragraph(f"RUC: {EMPRESA_RUC}", subtitulo_style))
    story.append(Paragraph(EMPRESA_DIRECCION, subtitulo_style))
    story.append(Spacer(1, 12))

    # Título del Comprobante
    story.append(Paragraph(f"<b>{tipo_doc.upper()}</b>", comprobante_style))
    story.append(Paragraph(f"<b>N° {serie_num}</b>", comprobante_style))
    story.append(Spacer(1, 10))

    # Datos del Cliente y Emisión
    fecha_str = fecha_emision if fecha_emision else datetime.now().strftime("%d/%m/%Y %H:%M")
    datos_cliente = [
        [Paragraph(f"<b>Cliente / Razón Social:</b> {cliente_nom}", normal_style)],
        [Paragraph(f"<b>DNI / RUC:</b> {cliente_doc}", normal_style)],
        [Paragraph(f"<b>Fecha de Emisión:</b> {fecha_str}", normal_style)],
    ]

    if doc_referencia:
        datos_cliente.append([Paragraph(f"<b>Comprobante Afectado:</b> {doc_referencia}", normal_style)])
    if motivo:
        datos_cliente.append([Paragraph(f"<b>Motivo / Sustento:</b> {motivo}", normal_style)])

    tabla_cli = Table(datos_cliente, colWidths=[535])
    tabla_cli.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tabla_cli)
    story.append(Spacer(1, 12))

    # Tabla de Ítems
    data_tabla = [[
        Paragraph("<b>Cant.</b>", normal_style),
        Paragraph("<b>Descripción del Producto</b>", normal_style),
        Paragraph("<b>P. Unit (S/.)</b>", derecha_style),
        Paragraph("<b>Subtotal (S/.)</b>", derecha_style),
    ]]

    for item in items:
        desc = item.get("descripcion") or item.get("productos", {}).get("descripcion", "Producto")
        cant = item.get("cantidad", 0)
        pu = float(item.get("precio_unitario", item.get("precio", 0.0)))
        sub = cant * pu

        data_tabla.append([
            Paragraph(str(cant), normal_style),
            Paragraph(desc, normal_style),
            Paragraph(f"{pu:.2f}", derecha_style),
            Paragraph(f"{sub:.2f}", derecha_style),
        ])

    tabla_prod = Table(data_tabla, colWidths=[55, 300, 90, 90])
    tabla_prod.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor("#475569")),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#475569")),
        ])
    )
    story.append(tabla_prod)
    story.append(Spacer(1, 10))

    # Totales
    data_totales = [
        [Paragraph("Op. Gravada:", derecha_style), Paragraph(f"S/. {subtotal:.2f}", derecha_style)],
        [Paragraph("IGV (18%):", derecha_style), Paragraph(f"S/. {igv:.2f}", derecha_style)],
        [Paragraph("<b>TOTAL A PAGAR:</b>", bold_derecha), Paragraph(f"<b>S/. {total_gen:.2f}</b>", bold_derecha)],
    ]
    tabla_totales = Table(data_totales, colWidths=[435, 100])
    tabla_totales.setStyle(TableStyle([
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LINEABOVE", (0, 2), (-1, 2), 0.8, colors.HexColor("#475569")),
    ]))
    story.append(tabla_totales)
    story.append(Spacer(1, 20))

    # Pie de página
    story.append(Paragraph(EMPRESA_MENSAJE_PIE, subtitulo_style))

    doc.build(story)
    return buffer.getvalue()

def mostrar_previsualizacion_pdf(pdf_bytes: bytes, height: int = 550) -> None:
    """
    Renderiza la previsualización del comprobante en Streamlit.
    1. Intenta renderizar como imagen nativa (pypdfium2 / pdf2image) para compatibilidad
       total en Streamlit Cloud, navegadores móviles, Chrome y Safari.
    2. Si no hay renderizador de imagen, usa fallback iframe base64.
    """
    st.markdown("### 👁️ Previsualización del Comprobante")

    # Intento 1: Renderizado con pypdfium2 (ultra rápido, sin dependencias del SO)
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_bytes)
        for i, page in enumerate(pdf):
            image = page.render(scale=2).to_pil()
            st.image(image, use_container_width=True, caption=f"Página {i+1}")
        return
    except Exception:
        pass

    # Intento 2: Renderizado con pdf2image (usando poppler de packages.txt)
    try:
        from pdf2image import convert_from_bytes
        images = convert_from_bytes(pdf_bytes, dpi=150)
        for i, img in enumerate(images):
            st.image(img, use_container_width=True, caption=f"Página {i+1}")
        return
    except Exception:
        pass

    # Intento 3: Fallback iframe base64
    base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="{height}" type="application/pdf" style="border: 1px solid #CBD5E1; border-radius: 8px;"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)
