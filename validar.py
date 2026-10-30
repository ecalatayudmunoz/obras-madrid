"""Validación de la Fase 1 con obras conocidas.

Busca cada obra de obras_conocidas.csv en la base (por expediente si se conoce, si no
por palabras del título) y muestra qué campos tenemos. Rellena el CSV con 20 obras
que conozcas bien y comprueba a mano que importe, empresa y plazos coinciden con la
fuente oficial.

Uso:  python validar.py [config.yaml]
"""
import csv
import sqlite3
import sys
from pathlib import Path

import yaml

from obras.placsp import clave_expediente, normalizar

cfg = yaml.safe_load(Path(sys.argv[1] if len(sys.argv) > 1 else "config.yaml").read_text(encoding="utf-8"))
con = sqlite3.connect(cfg["base_datos"])
con.create_function("norm", 1, normalizar)
con.row_factory = sqlite3.Row

encontradas = 0
conocidas = list(csv.DictReader(open("obras_conocidas.csv", encoding="utf-8")))
for ob in conocidas:
    if ob.get("expediente"):
        filas = con.execute("SELECT * FROM obras WHERE clave=?",
                            (clave_expediente(ob["expediente"]),)).fetchall()
    else:
        palabras = [normalizar(p) for p in ob["palabras"].split(";") if p.strip()]
        sql = "SELECT * FROM obras WHERE " + " AND ".join(["norm(titulo) LIKE ?"] * len(palabras))
        filas = con.execute(sql, [f"%{p}%" for p in palabras]).fetchall()

    marca = "✔" if filas else "✘"
    encontradas += bool(filas)
    print(f"\n{marca} {ob['nombre']}  ({len(filas)} expediente/s)")
    for f in filas[:3]:
        print(f"   {f['expediente']} · {f['estado_contrato']} · {f['empresa'] or '—'}")
        print(f"   licitación {f['presupuesto_licitacion']} € → adjudicación {f['importe_adjudicacion']} €"
              f" (baja {f['baja_pct']} %) · Excel municipal: {'sí' if f['en_excel_ayto'] else 'no'}")
        print(f"   {f['url_placsp']}")

print(f"\nEncontradas {encontradas} de {len(conocidas)}")
sys.exit(0 if encontradas else 1)
