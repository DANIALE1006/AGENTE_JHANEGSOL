"""
Servicio del Agente 2: Generador de Informes Gráficos y Reportes en PDF.
Genera informes ejecutivos de alta calidad visual con:
  - Membrete oficial de JHANEGSOL S.A.C.
  - Tarjetas de KPIs comerciales.
  - Gráficos estadísticos a color renderizados en alta resolución.
  - Tablas detalladas con formato contable.
  - Resumen analítico y recomendaciones de la IA.
"""
from __future__ import annotations
import io
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")  # Backend no interactivo para servidores/Streamlit
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.config import EMPRESA_DIRECCION, EMPRESA_NOMBRE, EMPRESA_RUC
from services.agent_data import (
    cargar_comprobantes,
    cargar_detalle_ventas,
    cargar_productos,
    obtener_metricas_ventas_rango,
)

ZONA_HORARIA = "America/Lima"
AZUL_PRIMARIO = "#0D47A1"
AZUL_CLARO = "#1976D2"
VERDE_EXITO = "#2E7D32"
NARANJA_ALERTA = "#F57C00"
GRIS_TEXTO = "#334155"


# ─────────────────────────── RENDERIZADO DE GRÁFICOS MATPLOTLIB ───────────────────────────

def _crear_grafico_ventas_diarias(diario: List[Dict[str, Any]]) -> Optional[bytes]:
    """Genera gráfico de barras/línea de ventas diarias en bytes PNG."""
    if not diario:
        return None
    df = pd.DataFrame(diario)
    if df.empty or "fecha" not in df.columns or "total" not in df.columns:
        return None

    df["fecha_dt"] = pd.to_datetime(df["fecha"]).dt.strftime("%d/%m")
    # Limitar a máximo 20 puntos para legibilidad
    if len(df) > 20:
        df = df.tail(20)

    fig, ax = plt.subplots(figsize=(7.5, 2.8), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    bars = ax.bar(df["fecha_dt"], df["total"], color="#1E88E5", edgecolor="#1565C0", width=0.6, alpha=0.9)
    ax.plot(df["fecha_dt"], df["total"], color="#0D47A1", marker="o", linewidth=2, markersize=4)

    ax.set_title("Evolución de Ventas Diarias (S/)", fontsize=11, fontweight="bold", color="#0F172A", pad=10)
    ax.set_ylabel("Monto (S/)", fontsize=9, color="#475569")
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.5, color="#CBD5E1")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CBD5E1")
    ax.spines["bottom"].set_color("#CBD5E1")

    # Etiquetas sobre barras más representativas
    max_val = df["total"].max()
    for bar in bars:
        h = bar.get_height()
        if h > 0 and (h >= max_val * 0.4 or len(df) <= 10):
            ax.annotate(f"S/{h:,.0f}",
                        xy=(bar.get_x() + bar.get_width() / 2, h),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=7, color="#0F172A", fontweight="semibold")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _crear_grafico_top_productos(top_prods: List[Dict[str, Any]]) -> Optional[bytes]:
    """Genera gráfico horizontal de productos más vendidos en bytes PNG."""
    if not top_prods:
        return None
    df = pd.DataFrame(top_prods[:8])
    if df.empty or "descripcion" not in df.columns:
        return None

    # Invertir para que el mayor quede arriba
    df = df.iloc[::-1]
    descripciones = [d[:28] + "..." if len(d) > 28 else d for d in df["descripcion"]]

    fig, ax = plt.subplots(figsize=(7.5, 3.0), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    bars = ax.barh(descripciones, df["ingresos"], color="#2E7D32", edgecolor="#1B5E20", height=0.55, alpha=0.85)
    ax.set_title("Top Productos por Recaudación (S/)", fontsize=11, fontweight="bold", color="#0F172A", pad=10)
    ax.set_xlabel("Ingresos Totales (S/)", fontsize=9, color="#475569")
    ax.tick_params(axis="both", labelsize=8)
    ax.grid(axis="x", linestyle="--", alpha=0.5, color="#CBD5E1")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#CBD5E1")
    ax.spines["bottom"].set_color("#CBD5E1")

    for bar, (_, row) in zip(bars, df.iterrows()):
        w = bar.get_width()
        u = row.get("unidades", 0)
        ax.annotate(f"S/{w:,.2f} ({int(u)} u.)",
                    xy=(w, bar.get_y() + bar.get_height() / 2),
                    xytext=(5, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=7.5, color="#1B5E20", fontweight="bold")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _crear_grafico_comprobantes(por_tipo: List[Dict[str, Any]]) -> Optional[bytes]:
    """Genera gráfico circular de distribución de ventas por comprobante."""
    if not por_tipo:
        return None
    df = pd.DataFrame(por_tipo)
    if df.empty or "tipo_comprobante" not in df.columns or "monto" not in df.columns:
        return None

    df = df[df["monto"] > 0]
    if df.empty:
        return None

    fig, ax = plt.subplots(figsize=(6.0, 2.5), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")

    colores = ["#0D47A1", "#2E7D32", "#F57C00", "#7B1FA2"][:len(df)]
    wedges, texts, autotexts = ax.pie(
        df["monto"],
        labels=df["tipo_comprobante"],
        autopct="%1.1f%%",
        startangle=140,
        colors=colores,
        textprops=dict(color="#0F172A", fontsize=8),
        wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2),
    )
    for at in autotexts:
        at.set_color("white")
        at.set_fontsize(8)
        at.set_fontweight("bold")

    ax.set_title("Distribución de Ventas por Tipo de Documento", fontsize=10, fontweight="bold", pad=8)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# ─────────────────────────── CONSTRUCCIÓN DEL DOCUMENTO PDF ───────────────────────────

def generar_pdf_informe_ventas(
    desde: date,
    hasta: date,
    titulo_personalizado: Optional[str] = None,
) -> bytes:
    """
    Construye un informe en PDF completo y profesional sobre ventas y rendimiento comercial.
    """
    ahora = datetime.now(ZoneInfo(ZONA_HORARIA))

    metricas = obtener_metricas_ventas_rango(desde, hasta)
    prods = cargar_productos()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    story = []
    styles = getSampleStyleSheet()

    # Estilos tipográficos
    estilo_empresa = ParagraphStyle(
        "Empresa",
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor(AZUL_PRIMARIO),
    )
    estilo_subempresa = ParagraphStyle(
        "SubEmpresa",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#64748B"),
    )
    estilo_titulo = ParagraphStyle(
        "TituloReporte",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )
    estilo_seccion = ParagraphStyle(
        "Seccion",
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor(AZUL_PRIMARIO),
        spaceBefore=10,
        spaceAfter=6,
    )
    estilo_normal = ParagraphStyle(
        "NormalTexto",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor(GRIS_TEXTO),
    )
    estilo_destacado = ParagraphStyle(
        "Destacado",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0F172A"),
    )
    estilo_kpi_num = ParagraphStyle(
        "KpiNum",
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        alignment=1,
        textColor=colors.HexColor(AZUL_PRIMARIO),
    )
    estilo_kpi_lbl = ParagraphStyle(
        "KpiLbl",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        alignment=1,
        textColor=colors.HexColor("#64748B"),
    )

    # 1. ENCABEZADO CORPORATIVO
    encabezado_data = [
        [
            Paragraph(f"<b>{EMPRESA_NOMBRE}</b><br/><font size=7.5 color='#64748B'>RUC: {EMPRESA_RUC} • {EMPRESA_DIRECCION}</font>", estilo_empresa),
            Paragraph(f"<b>INFORME EJECUTIVO DE VENTAS</b><br/><font size=7.5 color='#64748B'>Emisión: {ahora.strftime('%d/%m/%Y %H:%M')}<br/>Periodo: {desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}</font>", ParagraphStyle("HeaderRight", fontName="Helvetica", fontSize=8.5, leading=11, alignment=2)),
        ]
    ]
    t_encabezado = Table(encabezado_data, colWidths=[310, 212])
    t_encabezado.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(t_encabezado)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor(AZUL_PRIMARIO), spaceAfter=12))

    # 2. TARJETAS DE KPIS PRINCIPALES
    total_bruto = metricas["total_bruto"]
    total_neto = metricas["total_neto"]
    n_ventas = metricas["n_ventas"]
    ticket_prom = metricas["ticket_promedio"]
    quiebre_stock = int((prods["stock"] <= prods["stock_minimo"]).sum()) if not prods.empty else 0

    kpi_table_data = [
        [
            Paragraph("RECAUDACIÓN NETA", estilo_kpi_lbl),
            Paragraph("TOTAL FACTURADO", estilo_kpi_lbl),
            Paragraph("COMPROBANTES", estilo_kpi_lbl),
            Paragraph("TICKET PROMEDIO", estilo_kpi_lbl),
            Paragraph("STOCK CRÍTICO", estilo_kpi_lbl),
        ],
        [
            Paragraph(f"S/ {total_neto:,.2f}", ParagraphStyle("KpiNeto", parent=estilo_kpi_num, textColor=colors.HexColor(VERDE_EXITO))),
            Paragraph(f"S/ {total_bruto:,.2f}", estilo_kpi_num),
            Paragraph(f"{n_ventas}", estilo_kpi_num),
            Paragraph(f"S/ {ticket_prom:,.2f}", estilo_kpi_num),
            Paragraph(f"{quiebre_stock} prod.", ParagraphStyle("KpiCrit", parent=estilo_kpi_num, textColor=colors.HexColor(NARANJA_ALERTA if quiebre_stock else VERDE_EXITO))),
        ]
    ]
    t_kpis = Table(kpi_table_data, colWidths=[104, 104, 104, 105, 105])
    t_kpis.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(t_kpis)
    story.append(Spacer(1, 10))

    # 3. RESUMEN EJECUTIVO DEL AGENTE IA
    story.append(Paragraph("📌 Resumen Ejecutivo de la Inteligencia Artificial", estilo_seccion))
    if n_ventas > 0:
        desc_ia = (
            f"Durante el periodo evaluado del <b>{desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}</b>, "
            f"se concretaron <b>{n_ventas} transacciones comerciales</b> alcanzando una facturación neta de "
            f"<b>S/ {total_neto:,.2f}</b> (descontando S/ {metricas['total_notas']:,.2f} en notas de crédito). "
            f"El ticket promedio de compra se situó en <b>S/ {ticket_prom:,.2f}</b> por cliente. "
            f"El impuesto general a las ventas (IGV 18%) recaudado asciende a <b>S/ {metricas['igv_total']:,.2f}</b>."
        )
    else:
        desc_ia = (
            f"No se registraron ventas en el periodo del <b>{desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}</b>. "
            "Se sugiere verificar la conectividad de terminales de punto de venta y revisar las ofertas comerciales."
        )
    story.append(Paragraph(desc_ia, estilo_normal))
    story.append(Spacer(1, 10))

    # 4. GRÁFICOS MATPLOTLIB EN ALTA RESOLUCIÓN
    img_diaria = _crear_grafico_ventas_diarias(metricas["diario"])
    if img_diaria:
        story.append(Paragraph("📈 Evolución y Tendencia de Ventas Diarias", estilo_seccion))
        story.append(Image(io.BytesIO(img_diaria), width=520, height=195))
        story.append(Spacer(1, 10))

    img_top = _crear_grafico_top_productos(metricas["top_productos"])
    if img_top:
        story.append(Paragraph("🏆 Productos con Mayor Aporte a los Ingresos", estilo_seccion))
        story.append(Image(io.BytesIO(img_top), width=520, height=205))
        story.append(Spacer(1, 10))

    # 5. TABLA DE PRODUCTOS LÍDERES
    top_p = metricas["top_productos"][:10]
    if top_p:
        story.append(Paragraph("📋 Detalle de Artículos Más Vendidos", estilo_seccion))
        t_prod_data = [
            [
                Paragraph("<b>#</b>", estilo_destacado),
                Paragraph("<b>Código</b>", estilo_destacado),
                Paragraph("<b>Descripción del Producto</b>", estilo_destacado),
                Paragraph("<b>Unidades</b>", ParagraphStyle("R1", parent=estilo_destacado, alignment=2)),
                Paragraph("<b>Total (S/)</b>", ParagraphStyle("R2", parent=estilo_destacado, alignment=2)),
            ]
        ]
        for i, item in enumerate(top_p):
            t_prod_data.append([
                Paragraph(str(i + 1), estilo_normal),
                Paragraph(str(item.get("codigo", "")), estilo_normal),
                Paragraph(str(item.get("descripcion", "")), estilo_normal),
                Paragraph(f"{int(item.get('unidades', 0))}", ParagraphStyle("C1", parent=estilo_normal, alignment=2)),
                Paragraph(f"S/ {item.get('ingresos', 0.0):,.2f}", ParagraphStyle("C2", parent=estilo_normal, alignment=2)),
            ])
        t_prod = Table(t_prod_data, colWidths=[25, 75, 262, 70, 90])
        t_prod.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor(AZUL_PRIMARIO)),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_prod)
        story.append(Spacer(1, 12))

    # 6. GRÁFICO CIRCULAR DE COMPROBANTES Y DESGLOSE
    img_pie = _crear_grafico_comprobantes(metricas["por_tipo"])
    if img_pie:
        story.append(KeepTogether([
            Paragraph("📊 Composición de la Facturación por Tipo de Documento", estilo_seccion),
            Image(io.BytesIO(img_pie), width=420, height=175),
            Spacer(1, 10),
        ]))

    # 7. CONCLUSIONES Y RECOMENDACIONES ESTRATÉGICAS
    story.append(Paragraph("🎯 Recomendaciones Estratégicas del Agente", estilo_seccion))
    recs = [
        f"• <b>Monitoreo de Quiebres:</b> Existen {quiebre_stock} productos en stock mínimo o agotado. Priorizar la reposición de los productos del Top 5 para evitar ventas perdidas.",
        f"• <b>Optimización del Ticket Promedio:</b> El ticket actual es de S/ {ticket_prom:,.2f}. Diseñar combos de productos complementarios con margen alto para elevar el valor por compra.",
        "• <b>Gestión de Inventario Inmovilizado:</b> Identificar artículos sin rotación reciente y activar promociones de liquidación para liberar liquidez de trabajo.",
    ]
    for r in recs:
        story.append(Paragraph(r, estilo_normal))
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CBD5E1"), spaceAfter=8))
    story.append(Paragraph(
        "Documento emitido electrónicamente por el Sistema Multi-Agente IA JHANEGSOL S.A.C. "
        "• Huacho, Lima - Perú • Válido para control interno gerencial.",
        ParagraphStyle("Pie", fontName="Helvetica", fontSize=7, leading=9, alignment=1, textColor=colors.HexColor("#94A3B8"))
    ))

    doc.build(story)
    return buffer.getvalue()


def generar_pdf_informe_inventario() -> bytes:
    """
    Construye un informe en PDF completo sobre el inventario, valorizaciones y stock crítico.
    """
    ahora = datetime.now(ZoneInfo(ZONA_HORARIA))
    df = cargar_productos()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    story = []
    styles = getSampleStyleSheet()

    estilo_empresa = ParagraphStyle("Emp", fontName="Helvetica-Bold", fontSize=14, leading=17, textColor=colors.HexColor(AZUL_PRIMARIO))
    estilo_seccion = ParagraphStyle("Sec", fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=colors.HexColor(AZUL_PRIMARIO), spaceBefore=10, spaceAfter=6)
    estilo_normal = ParagraphStyle("Norm", fontName="Helvetica", fontSize=8.5, leading=12, textColor=colors.HexColor(GRIS_TEXTO))
    estilo_dest = ParagraphStyle("Dest", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=colors.HexColor("#0F172A"))

    # Encabezado
    story.append(Table([
        [
            Paragraph(f"<b>{EMPRESA_NOMBRE}</b><br/><font size=7.5 color='#64748B'>RUC: {EMPRESA_RUC} • {EMPRESA_DIRECCION}</font>", estilo_empresa),
            Paragraph(f"<b>INFORME DE INVENTARIO Y STOCK</b><br/><font size=7.5 color='#64748B'>Corte: {ahora.strftime('%d/%m/%Y %H:%M')}</font>", ParagraphStyle("Hdr", fontName="Helvetica", fontSize=8.5, leading=11, alignment=2)),
        ]
    ], colWidths=[310, 212]))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor(AZUL_PRIMARIO), spaceAfter=12))

    if df.empty:
        story.append(Paragraph("No hay productos registrados en la base de datos.", estilo_normal))
        doc.build(story)
        return buffer.getvalue()

    total_prods = len(df)
    total_unidades = int(df["stock"].sum())
    valor_costo = df["valor_costo"].sum()
    valor_venta = df["valor_venta"].sum()
    criticos = df[df["stock"] <= df["stock_minimo"]]

    # KPIs de Almacén
    kpis = [
        [Paragraph("PRODUCTOS", estilo_dest), Paragraph("UNIDADES EN STOCK", estilo_dest), Paragraph("VALORIZACIÓN COSTO", estilo_dest), Paragraph("VALORIZACIÓN VENTA", estilo_dest)],
        [Paragraph(f"{total_prods}", estilo_dest), Paragraph(f"{total_unidades:,}", estilo_dest), Paragraph(f"S/ {valor_costo:,.2f}", estilo_dest), Paragraph(f"S/ {valor_venta:,.2f}", estilo_dest)],
    ]
    t_kpis = Table(kpis, colWidths=[130, 130, 131, 131])
    t_kpis.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t_kpis)
    story.append(Spacer(1, 12))

    # Alertas de stock crítico
    story.append(Paragraph(f"🚨 Alerta de Reposición ({len(criticos)} productos en o bajo stock mínimo)", estilo_seccion))
    if not criticos.empty:
        t_crit_data = [[
            Paragraph("<b>Código</b>", estilo_dest),
            Paragraph("<b>Descripción</b>", estilo_dest),
            Paragraph("<b>Stock</b>", estilo_dest),
            Paragraph("<b>Mínimo</b>", estilo_dest),
            Paragraph("<b>Proveedor</b>", estilo_dest),
        ]]
        for _, r in criticos.head(15).iterrows():
            t_crit_data.append([
                Paragraph(str(r["codigo"]), estilo_normal),
                Paragraph(str(r["descripcion"]), estilo_normal),
                Paragraph(f"<b>{int(r['stock'])}</b>", ParagraphStyle("Stk", parent=estilo_normal, textColor=colors.HexColor(NARANJA_ALERTA))),
                Paragraph(f"{int(r['stock_minimo'])}", estilo_normal),
                Paragraph(str(r.get("proveedor", "N/A")), estilo_normal),
            ])
        t_crit = Table(t_crit_data, colWidths=[80, 242, 60, 60, 80])
        t_crit.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FFF7ED")),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor(NARANJA_ALERTA)),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#FED7AA")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_crit)
    else:
        story.append(Paragraph("✅ Todos los productos cuentan con niveles de stock óptimos.", estilo_normal))

    doc.build(story)
    return buffer.getvalue()
