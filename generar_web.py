"""Genera la web estática a partir de la base de datos.

Salida en publicar/ (lo que se sube a GitHub Pages):
    publicar/index.html
    publicar/data/obras.json   datos de la web
    publicar/data/obras.csv    datos abiertos

Uso:
    python generar_web.py
    python generar_web.py --config tests/config_demo.yaml --inline vista_previa.html --aviso "Datos de ejemplo"
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from obras.web import construir

RAIZ = Path(__file__).parent
PLANTILLA = RAIZ / "sitio" / "index.html"
CABECERA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>
</head>
<body>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--salida", default="publicar")
    ap.add_argument("--inline", help="genera además un único HTML con los datos dentro (vista previa)")
    ap.add_argument("--aviso", help="franja de aviso en la cabecera (p. ej. 'Datos de ejemplo')")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    con = sqlite3.connect(cfg["base_datos"])
    obras = construir(con)
    ultima = con.execute("SELECT MAX(fin) FROM cargas WHERE estado='ok'").fetchone()[0]
    meta = {"generado": (ultima or datetime.now(timezone.utc).isoformat())[:10], "total": len(obras),
            "aviso": args.aviso}
    datos = {"meta": meta, "obras": obras}

    salida = Path(args.salida)
    (salida / "data").mkdir(parents=True, exist_ok=True)
    (salida / "data" / "obras.json").write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")),
                                                encoding="utf-8")
    plana = [{k: v for k, v in o.items() if k not in ("fuentes", "historial")} |
             {"url_fuente": next((f["url"] for f in o["fuentes"] if f["url"]), None)} for o in obras]
    pd.DataFrame(plana).to_csv(salida / "data" / "obras.csv", index=False, encoding="utf-8")

    plantilla = PLANTILLA.read_text(encoding="utf-8")
    (salida / "index.html").write_text(CABECERA + plantilla + "\n</body>\n</html>\n", encoding="utf-8")
    (salida / ".nojekyll").write_text("")
    print(f"Web generada en {salida}/ con {len(obras)} obras")

    if args.inline:
        meta_prev = meta | {"prevista": True}
        js = json.dumps({"meta": meta_prev, "obras": obras}, ensure_ascii=False).replace("</", "<\\/")
        Path(args.inline).write_text(plantilla.replace("/*DATOS*/null/*FIN*/", js), encoding="utf-8")
        print(f"Vista previa en {args.inline}")


if __name__ == "__main__":
    main()
