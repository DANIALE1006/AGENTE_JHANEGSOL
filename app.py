Entrypoint alternativo para Streamlit Cloud / Hosting.
Funciona aunque el proyecto esté dentro de una subcarpeta.
"""
import os
import runpy
import sys

BASE = os.path.dirname(os.path.abspath(_file_))
os.chdir(BASE)
if BASE not in sys.path:
    sys.path.insert(0, BASE)

if _name_ == "_main_":
    runpy.run_path(os.path.join(BASE, "INVENTARIO-JHANEGSOL-OK.py"), run_name="_main_")
