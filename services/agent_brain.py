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

SYSTEM_BASE = """Eres "Jhani", el consultor de inteligencia comercial del Sistema Multi-Agente de JHANEGSOL S.A.C. (Huacho, Perú).
El sistema cuenta con 3 agentes especializados:
1. Agente 1 (Email & Notificador): Envía por correo electrónico la situación de las ventas a pedido y automáticamente a las 8:00 AM (ventas de ayer) y a las 5:00 PM (cierre de hoy). Usa `enviar_reporte_ventas_correo` o `enviar_correo_gmail`.
2. Agente 2 (Informes Gráficos y PDF): Genera informes visuales interactivos y compila reportes ejecutivos descargables en PDF con gráficos y tablas. Usa `generar_informe_grafico_pdf`.
3. Agente 3 (Consultor Q&A): Responde preguntas comerciales, analiza ventas, stock, clientes, márgenes y explica conceptos.

Reglas:
- Tienes PERMISO EXPLÍCITO para enviar reportes por correo usando `enviar_reporte_ventas_correo` o `enviar_correo_gmail`.
- Si el usuario te pide enviar un reporte o situación de ventas por correo, ejecuta la herramienta correspondiente.
- Si el usuario te pide generar un reporte o informe en PDF con gráficos, ejecuta `generar_informe_grafico_pdf`.
- Usa SIEMPRE las herramientas para obtener datos precisos de la empresa; nunca inventes cifras.
- Base de datos: eres de solo lectura (no modificas stock ni emites comprobantes desde el chat).
- Moneda: soles (S/). Los precios incluyen IGV 18%.
- Responde en español, con formato Markdown estructurado, claro y emojis moderados.
- Cierra con una sugerencia de siguiente pregunta útil o acción recomendada.
Estilo pedido: {estilo}"""


def _secreto(nombre: str) -> str:
    try:
        import streamlit as st
        if hasattr(st, "secrets") and nombre in st.secrets:
            return str(st.secrets[nombre])
    except Exception:
        pass
    return os.getenv(nombre, "")


def proveedor_ia() -> str:
    """Devuelve 'groq', 'openai', 'anthropic' o '' segun las claves configuradas."""
    if _secreto("GROQ_API_KEY"):
        try:
            import openai  # noqa: F401
            return "groq"
        except ImportError:
            pass
    if _secreto("OPENAI_API_KEY"):
        try:
            import openai  # noqa: F401
            return "openai"
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
                r = ejecutar_herramienta(bloque.name, bloque.input)
                usados.append({"nombre": bloque.name, "args": bloque.input, "resultado": r})
                resultados.append({"type": "tool_result", "tool_use_id": bloque.id, "content": _para_modelo(r)})
        mensajes.append({"role": "user", "content": resultados})
    return "Consulté varias fuentes pero no llegué a una conclusión. ¿Puedes precisar la pregunta?", usados


# ─────────────────────────── MODO IA (Groq) ───────────────────────────

def _tools_formato_openai():
    return [{"type": "function",
             "function": {"name": t["name"], "description": t["description"],
                          "parameters": t["input_schema"]}} for t in TOOL_SPECS]


def responder_con_groq(historial: List[Dict[str, str]], estilo: str) -> Tuple[str, List[Dict[str, Any]]]:
    from openai import OpenAI

    client = OpenAI(api_key=_secreto("GROQ_API_KEY"), base_url=GROQ_BASE_URL)
    modelo = _secreto("GROQ_MODEL") or MODELO_GROQ_POR_DEFECTO
    system = SYSTEM_BASE.format(estilo=ESTILOS.get(estilo, ""))
    mensajes: List[Dict[str, Any]] = [{"role": "system", "content": system}]
    mensajes += [{"role": m["role"], "content": m["content"]} for m in historial[-12:]]
    usados: List[Dict[str, Any]] = []
    tools = _tools_formato_openai()

    for _ in range(6):  # maximo 6 rondas de herramientas
        resp = client.chat.completions.create(model=modelo, messages=mensajes, tools=tools,
                                              tool_choice="auto", max_tokens=1500, temperature=0.3)
        msg = resp.choices[0].message
        llamadas = msg.tool_calls or []
        if not llamadas:
            return (msg.content or "No tengo una respuesta para eso.").strip(), usados
        mensajes.append({
            "role": "assistant", "content": msg.content or "",
            "tool_calls": [{"id": c.id, "type": "function",
                            "function": {"name": c.function.name, "arguments": c.function.arguments or "{}"}}
                           for c in llamadas],
        })
        for c in llamadas:
            try:
                args = json.loads(c.function.arguments or "{}") or {}
            except json.JSONDecodeError:
                args = {}
            r = ejecutar_herramienta(c.function.name, args)
            usados.append({"nombre": c.function.name, "args": args, "resultado": r})
            mensajes.append({"role": "tool", "tool_call_id": c.id, "content": _para_modelo(r)})
    return "Consulte varias fuentes pero no llegue a una conclusion. ¿Puedes precisar la pregunta?", usados


# ─────────────────────────── MODO LOCAL ───────────────────────────

def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


REGLAS = [
    ("enviar_correo_gmail", ["enviar correo", "manda correo", "enviar email", "mandar email", "envia un correo", "manda un correo", "notificar correo"]),
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
    if "hoy" in t or "ayer" in t:
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
    
    # Detección especial para Agente 2: Informes y PDF
    if any(k in t for k in ["pdf", "descargar informe", "informe grafico", "descargar reporte", "informe en pdf", "reporte pdf"]):
        dias = _extraer_dias(pregunta) or 30
        return "generar_informe_grafico_pdf", {"dias": dias}

    # Detección especial para Agente 1: Envío de correo
    if any(k in t for k in ["correo", "email", "mail"]):
        if "ayer" in t:
            periodo = "ayer"
        elif "semana" in t:
            periodo = "semana"
        elif "mes" in t:
            periodo = "mes"
        else:
            periodo = "hoy"
        return "enviar_reporte_ventas_correo", {"periodo": periodo}

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
                "clientes, márgenes, análisis ABC, productos sin movimiento, reposición, enviar correo* o *buscar <producto>*. "
                "Prueba con uno de los botones de acceso rápido 👆"), []
    r = ejecutar_herramienta(herramienta, args)
    texto = f"### {r.get('titulo', '')}\n{r.get('resumen', '')}"
    if r.get("consejo"):
        texto += f"\n\n> 💡 **Dato para aprender:** {r['consejo']}"
    return texto, [{"nombre": herramienta, "args": args, "resultado": r}]


def responder(historial: List[Dict[str, str]], estilo: str, usar_ia: bool) -> Tuple[str, List[Dict[str, Any]], str]:
    """Devuelve (texto, herramientas_usadas, modo)."""
    proveedor = proveedor_ia()
    if usar_ia and proveedor:
        try:
            if proveedor == "groq":
                texto, usados = responder_con_groq(historial, estilo)
            elif proveedor == "openai":
                from openai import OpenAI
                client = OpenAI(api_key=_secreto("OPENAI_API_KEY"))
                modelo = _secreto("OPENAI_MODEL") or "gpt-4o-mini"
                system = SYSTEM_BASE.format(estilo=ESTILOS.get(estilo, ""))
                mensajes = [{"role": "system", "content": system}] + [{"role": m["role"], "content": m["content"]} for m in historial[-12:]]
                usados = []
                tools = _tools_formato_openai()
                for _ in range(6):
                    resp = client.chat.completions.create(model=modelo, messages=mensajes, tools=tools, tool_choice="auto", max_tokens=1500, temperature=0.3)
                    msg = resp.choices[0].message
                    llamadas = msg.tool_calls or []
                    if not llamadas:
                        texto = (msg.content or "No tengo una respuesta para eso.").strip()
                        break
                    mensajes.append({"role": "assistant", "content": msg.content or "", "tool_calls": [{"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments or "{}"}} for c in llamadas]})
                    for c in llamadas:
                        try:
                            args = json.loads(c.function.arguments or "{}") or {}
                        except json.JSONDecodeError:
                            args = {}
                        r = ejecutar_herramienta(c.function.name, args)
                        usados.append({"nombre": c.function.name, "args": args, "resultado": r})
                        mensajes.append({"role": "tool", "tool_call_id": c.id, "content": _para_modelo(r)})
                else:
                    texto = "Consulté varias fuentes pero no llegué a una conclusión definitiva."
            else:
                texto, usados = responder_con_ia(historial, estilo)
            return texto, usados, "ia"
        except Exception as e:
            texto, usados = responder_local(historial[-1]["content"])
            return f"⚠️ La IA no respondió ({type(e).__name__}); uso el modo local.\n\n{texto}", usados, "local"
    texto, usados = responder_local(historial[-1]["content"])
    return texto, usados, "local"
