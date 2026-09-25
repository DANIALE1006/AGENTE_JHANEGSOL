"""
Cerebro del Agente Jhanegsol IA.

- Modo IA: usa Claude (API de Anthropic) con herramientas (tool use).
- Modo local: si no hay API key, interpreta la pregunta con palabras clave
  y ejecuta la herramienta adecuada. Funciona gratis y sin internet externo.
"""
from __future__ import annotations
import json
import os
import re
import unicodedata
from typing import Any, Dict, List, Tuple

from services.agent_tools import TOOL_SPECS, ejecutar_herramienta

MODELO_POR_DEFECTO = "claude-haiku-4-5"

ESTILOS = {
    "🎓 Didáctico": "Explica como un profesor paciente: define los conceptos (margen, rotación, punto de reorden) "
                   "con ejemplos sencillos usando los datos reales, y termina con un 'Dato para aprender'.",
    "💼 Ejecutivo": "Responde como un gerente: máximo 5 líneas, cifras clave y una acción concreta.",
    "🔍 Detallado": "Responde como un analista: desglosa cifras, compara, señala riesgos y da 3 recomendaciones.",
}

SYSTEM_BASE = """Eres "Jhani", el agente de inteligencia comercial de JHANEGSOL S.A.C. (Huacho, Perú).
Ayudas a gestionar inventario, ventas, compras y clientes. Moneda: soles (S/). Los precios incluyen IGV 18%.
Reglas:
- Usa SIEMPRE las herramientas para obtener datos; nunca inventes cifras.
- Eres de solo lectura: no puedes registrar ventas ni modificar stock. Si te lo piden, indica el módulo del sistema que deben usar.
- Responde en español, con formato Markdown breve y emojis moderados.
- Cierra con una sugerencia de siguiente pregunta útil.
Estilo pedido: {estilo}"""


def _secreto(nombre: str) -> str:
    try:
        import streamlit as st
        if nombre in st.secrets:
            return str(st.secrets[nombre])
    except Exception:
        pass
    return os.getenv(nombre, "")


def ia_disponible() -> bool:
    if not _secreto("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


# ─────────────────────────── MODO IA (Claude) ───────────────────────────

def _para_modelo(resultado: Dict[str, Any]) -> str:
    """Resume el resultado de una herramienta para enviarlo al modelo (sin gráficos, tabla recortada)."""
    compacto = {k: v for k, v in resultado.items() if k in ("titulo", "resumen", "consejo")}
    if resultado.get("tabla"):
        compacto["tabla"] = resultado["tabla"][:25]
    return json.dumps(compacto, ensure_ascii=False, default=str)


def responder_con_ia(historial: List[Dict[str, str]], estilo: str) -> Tuple[str, List[Dict[str, Any]]]:
    import anthropic

    client = anthropic.Anthropic(api_key=_secreto("ANTHROPIC_API_KEY"))
    modelo = _secreto("ANTHROPIC_MODEL") or MODELO_POR_DEFECTO
    system = SYSTEM_BASE.format(estilo=ESTILOS.get(estilo, ""))
    mensajes: List[Dict[str, Any]] = [{"role": m["role"], "content": m["content"]} for m in historial[-12:]]
    usados: List[Dict[str, Any]] = []

    for _ in range(6):  # máximo 6 rondas de herramientas
        resp = client.messages.create(model=modelo, max_tokens=1500, system=system,
                                      tools=TOOL_SPECS, messages=mensajes)
        if resp.stop_reason != "tool_use":
            texto = "".join(b.text for b in resp.content if b.type == "text").strip()
            return texto or "No tengo una respuesta para eso.", usados
        mensajes.append({"role": "assistant", "content": resp.content})
        resultados = []
        for bloque in resp.content:
            if bloque.type == "tool_use":
                r = ejecutar_herramienta(bloque.name, bloque.input)
                usados.append({"nombre": bloque.name, "args": bloque.input, "resultado": r})
                resultados.append({"type": "tool_result", "tool_use_id": bloque.id, "content": _para_modelo(r)})
        mensajes.append({"role": "user", "content": resultados})
    return "Consulté varias fuentes pero no llegué a una conclusión. ¿Puedes precisar la pregunta?", usados


# ─────────────────────────── MODO LOCAL ───────────────────────────

def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


REGLAS = [
    ("sugerir_reposicion", ["repon", "pedir", "pedido", "comprar", "reorden", "abastec"]),
    ("productos_bajo_stock", ["bajo stock", "agot", "quiebre", "falta", "minimo", "alerta", "critico"]),
    ("analisis_abc", ["abc", "pareto", "importantes", "clasific"]),
    ("productos_sin_movimiento", ["sin movimiento", "no se vend", "inmoviliz", "parado", "estancad", "quieto"]),
    ("analisis_margenes", ["margen", "ganancia por", "rentab", "perdida", "utilidad"]),
    ("top_clientes", ["cliente"]),
    ("top_productos", ["mas vendid", "top", "mejor vend", "estrella", "populares"]),
    ("resumen_inventario", ["inventario", "almacen", "valor del stock", "cuanto tengo", "general"]),
    ("resumen_ventas", ["venta", "vendimos", "factur", "ingreso", "ticket", "hoy", "semana", "mes"]),
]


def _extraer_dias(texto: str) -> int | None:
    t = _norm(texto)
    if "hoy" in t:
        return 1
    if "semana" in t:
        return 7
    m = re.search(r"(\d+)\s*(dia|mes|año|ano)", t)
    if m:
        n = int(m.group(1))
        return n * 30 if m.group(2) == "mes" else n * 365 if m.group(2) in ("año", "ano") else n
    if "mes" in t:
        return 30
    if "trimestre" in t:
        return 90
    return None


def interpretar_local(pregunta: str) -> Tuple[str, Dict[str, Any]]:
    t = _norm(pregunta)
    m = re.search(r"(?:busca|buscar|precio de|stock de|informacion de)\s+(.+)", t)
    if m and not any(k in t for k in ["bajo stock", "sin movimiento"]):
        return "buscar_producto", {"texto": m.group(1).strip(" ?¿.!")}
    for herramienta, claves in REGLAS:
        if any(k in t for k in claves):
            args: Dict[str, Any] = {}
            dias = _extraer_dias(pregunta)
            if dias and herramienta in ("resumen_ventas", "top_productos", "analisis_abc",
                                        "productos_sin_movimiento", "top_clientes"):
                args["dias"] = dias
            return herramienta, args
    return "", {}


def responder_local(pregunta: str) -> Tuple[str, List[Dict[str, Any]]]:
    herramienta, args = interpretar_local(pregunta)
    if not herramienta:
        return ("🤔 En **modo local** entiendo preguntas sobre: *inventario, stock bajo, ventas, más vendidos, "
                "clientes, márgenes, análisis ABC, productos sin movimiento, reposición* o *buscar <producto>*. "
                "Prueba con uno de los botones de acceso rápido 👆"), []
    r = ejecutar_herramienta(herramienta, args)
    texto = f"### {r.get('titulo', '')}\n{r.get('resumen', '')}"
    if r.get("consejo"):
        texto += f"\n\n> 💡 **Dato para aprender:** {r['consejo']}"
    return texto, [{"nombre": herramienta, "args": args, "resultado": r}]


def responder(historial: List[Dict[str, str]], estilo: str, usar_ia: bool) -> Tuple[str, List[Dict[str, Any]], str]:
    """Devuelve (texto, herramientas_usadas, modo)."""
    if usar_ia and ia_disponible():
        try:
            texto, usados = responder_con_ia(historial, estilo)
            return texto, usados, "ia"
        except Exception as e:
            texto, usados = responder_local(historial[-1]["content"])
            return f"⚠️ La IA no respondió ({type(e).__name__}); uso el modo local.\n\n{texto}", usados, "local"
    texto, usados = responder_local(historial[-1]["content"])
    return texto, usados, "local"
