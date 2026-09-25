# Entrypoint para Streamlit Cloud.
# Busca INVENTARIO-JHANEGSOL-OK.py en la raiz o en una subcarpeta y lo ejecuta.
import glob
import os
import runpy
import sys

RAIZ = os.path.dirname(os.path.abspath(_file_))
NOMBRE = "INVENTARIO-JHANEGSOL-OK.py"

candidatos = [os.path.join(RAIZ, NOMBRE)] + glob.glob(os.path.join(RAIZ, "*", NOMBRE))
principal = next((c for c in candidatos if os.path.isfile(c)), None)

if principal is None:
    raise FileNotFoundError("No se encontro " + NOMBRE + " en " + RAIZ)

CARPETA = os.path.dirname(principal)
os.chdir(CARPETA)
if CARPETA not in sys.path:
    sys.path.insert(0, CARPETA)

runpy.run_path(principal, run_name="_main_")
