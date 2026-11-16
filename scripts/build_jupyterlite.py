"""
Genera los cuadernos de Jupyter y la versión de Jupyter que corre en el navegador (JupyterLite).

    pip install "jupyterlite-core==0.6.*" "jupyterlite-pyodide-kernel==0.6.*"
    python scripts/build_jupyterlite.py

Resultado:
  notebooks/Golfo_Mexico_MIA_es.ipynb, _en.ipynb   cuadernos para Jupyter local (kernel python3)
  jupyterlite/                                     sitio estático que la API sirve en /jupyter (≈ 25 MB)

En JupyterLite el Python (Pyodide, WebAssembly) se ejecuta en el navegador de cada visitante: el servidor solo
entrega archivos estáticos, así que publicar /jupyter no permite ejecutar código en esta computadora. Pyodide y las
librerías (numpy, pandas, matplotlib…) se descargan del CDN de jsDelivr la primera vez.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend.notebook import construir_cuaderno, nombre_archivo  # noqa: E402

SALIDA = RAIZ / "jupyterlite"
CUADERNOS = RAIZ / "notebooks"
IDIOMAS = ("es", "en")


def escribir(nb: dict, ruta: Path) -> None:
    ruta.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cuadernos_locales() -> None:
    CUADERNOS.mkdir(exist_ok=True)
    for lang in IDIOMAS:
        ruta = CUADERNOS / nombre_archivo(lang)
        escribir(construir_cuaderno(lang, destino="local"), ruta)
        print("cuaderno:", ruta.relative_to(RAIZ))


def rutas_labextensions() -> list[str]:
    """Carpetas share/jupyter/labextensions visibles (instalaciones con --target, venvs, etc.)."""
    vistas = []
    for p in [sys.prefix, *sys.path]:
        c = Path(p) / "share" / "jupyter" / "labextensions"
        if c.is_dir() and str(c) not in vistas:
            vistas.append(str(c))
    return vistas


def construir_lite() -> None:
    from jupyterlite_core import manager
    try:
        import sqlite3  # noqa: F401
    except ImportError:   # p. ej. Windows con Control de aplicaciones: la caché de compilación usa JSON
        manager.LiteManager._trait_default_generators["_doit_config"] = lambda self: {
            "dep_file": ".jupyterlite.doit.json", "backend": "json", "verbosity": 1}
    from jupyterlite_core.app import main

    with tempfile.TemporaryDirectory(prefix="golfo_lite_") as tmp:
        lite = Path(tmp)
        contenido = lite / "files"
        contenido.mkdir()
        for lang in IDIOMAS:
            escribir(construir_cuaderno(lang, destino="lite"), contenido / nombre_archivo(lang))
        (lite / "jupyter-lite.json").write_text(json.dumps({
            "jupyter-lite-schema-version": 0,
            "jupyter-config-data": {"appName": "Golfo de México · Jupyter", "exposeAppInBrowser": True,
                                    "defaultKernelName": "python"},
        }), encoding="utf-8")
        temporal = lite / "_salida"
        sys.argv = ["jupyter-lite", "build", "--lite-dir", str(lite), "--contents", str(contenido),
                    "--output-dir", str(temporal), "--apps", "lab", "--apps", "notebooks", "--apps", "tree",
                    "--no-sourcemaps", "--no-unused-shared-packages",
                    *(f"--FederatedExtensionAddon.extra_labextensions_path={p}" for p in rutas_labextensions())]
        try:
            main()
        except SystemExit as fin:
            if fin.code not in (0, None):
                raise
        # Se compila en una carpeta temporal y luego se copia: JupyterLite borra su carpeta de salida y en carpetas
        # sincronizadas (OneDrive) borrar carpetas puede fallar: se borra lo que se pueda y se sobrescribe el resto.
        SALIDA.mkdir(exist_ok=True)
        for hijo in SALIDA.iterdir():
            shutil.rmtree(hijo, ignore_errors=True) if hijo.is_dir() else hijo.unlink(missing_ok=True)
        shutil.copytree(temporal, SALIDA, dirs_exist_ok=True)
    tam = sum(f.stat().st_size for f in SALIDA.rglob("*") if f.is_file()) / 1e6
    print(f"JupyterLite: {SALIDA.relative_to(RAIZ)}/ ({tam:.1f} MB) → servido en /jupyter")


if __name__ == "__main__":
    cuadernos_locales()
    construir_lite()
