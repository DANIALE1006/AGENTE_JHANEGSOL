"""
Cerebro del Agente Jhanegsol IA.

- Modo IA: usa Groq (GROQ_API_KEY) o Claude (ANTHROPIC_API_KEY) con herramientas (tool use).
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
MODELO_GROQ_POR_DEFECTO = "openai/gpt-oss-120b"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

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


def proveedor_ia() -> str:
    """Devuelve 'groq', 'anthropic' o '' segun las claves configuradas en Secrets."""
    if _secreto("GROQ_API_KEY"):
        try:
            import openai  # noqa: F401
            return "groq"
        except ImportError:
            pass
    if _secreto("ANTHROPIC_API_KEY"):
        try:
            import anthropic  # noqa: F401
            return "anthropic"
        except ImportError:
            pass
    return ""


def ia_disponible() -> bool:
    return proveedor_ia() != ""


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
                r = ejecutar_herramienta(bloque.name, bloque.
