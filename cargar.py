"""Carga diaria · Fase 1 (prueba de datos).

1. Descarga el ATOM de la PLACSP (feed actual + meses configurados).
2. Se queda con los contratos de Obras de órganos del Ayuntamiento de Madrid.
3. Lee el Excel municipal de obras en ejecución.
4. Guarda todo en SQLite con histórico y cruza por número de expediente.
5. Exporta datos/obras.csv y datos/informe_cruce.md.

Si una fuente falla o cambia de formato, no se toca la base y el proceso termina
con código 1 (GitHub Actions lo marca en rojo y avisa por email).

Uso:
    python cargar.py                       # todo según config.yaml
    python cargar.py --atom fichero.atom   # probar con un ATOM local
    python cargar.py --sin-excel
    python cargar.py --desde 2012          # carga histórica (una vez; tarda horas)
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from obras import db
from obras.excel_ayto import leer_excel_obras
from obras.placsp import (FuenteError, clave_expediente, es_de_madrid, leer_feed_paginado,
                          leer_zip_mensual, parsear_feed, periodos_desde)


def periodos_recientes(n: int) -> list[str]:
    """Los n meses anteriores al actual (la carga diaria repasa los últimos cambios)."""
    hoy = date.today()
    out = []
    for i in range(n, 0, -1):
        a, m = divmod(hoy.year * 12 + hoy.month - 1 - i, 12)
        out.append(f"{a}{m + 1:02d}")
    return out


def recoger_placsp(cfg: dict, atom_local: list[str], desde: str | None = None) -> dict[str, dict]:
    p, f = cfg["placsp"], cfg["filtro"]
    if atom_local:
        fuentes = [parsear_feed(Path(a).read_bytes())[0] for a in atom_local]
    else:
        periodos = periodos_desde(desde) if desde else periodos_recientes(p.get("meses_recientes", 2))
        print("Periodos PLACSP:", ", ".join(periodos))
        fuentes = [leer_zip_mensual(p["zip_mensual"].format(yyyymm=m)) for m in periodos]
        fuentes.append(leer_feed_paginado(p["feed_actual"], p.get("max_paginas", 0)))

    elegidos: dict[str, dict] = {}
    vistos = 0
    for fuente in fuentes:
        for exp in fuente:
            vistos += 1
            if exp.tipo_contrato not in f["tipos_contrato"]:
                continue
            if not es_de_madrid(exp, f["organos_incluir"], f.get("organos_excluir", [])):
                continue
            clave = clave_expediente(exp.expediente)
            if not clave:
                continue
            d = exp.to_dict()
            # Un expediente aparece varias veces (cada actualización): se queda la más reciente
            prev = elegidos.get(clave)
            if prev is None or (d["actualizado_fuente"] or "") >= (prev["actualizado_fuente"] or ""):
                elegidos[clave] = d
    print(f"PLACSP: {vistos} entradas leídas, {len(elegidos)} obras del Ayuntamiento de Madrid")
    return elegidos


def informe(con, ruta: Path) -> str:
    obras = pd.read_sql("SELECT * FROM obras", con)
    excel = pd.read_sql("SELECT clave FROM registros WHERE fuente='excel_obras'", con)
    sin_placsp = sorted(set(excel["clave"]) - set(obras["clave"]))
    cruzadas = int(obras["en_excel_ayto"].sum()) if len(obras) else 0

    lineas = [
        "# Informe de cruce · Fase 1", "",
        f"- Obras municipales en PLACSP: **{len(obras)}**",
        f"- Obras en el Excel municipal: **{len(excel)}**",
        f"- Cruzadas por expediente: **{cruzadas}**",
        f"- En el Excel pero no en PLACSP: **{len(sin_placsp)}** "
        "(normal si se adjudicaron antes de los meses cargados)", "",
        "## Por estado del contrato", "",
        obras["estado_contrato"].value_counts().to_markdown() if len(obras) else "_sin datos_", "",
        "## Primeras 20 claves del Excel sin pareja en PLACSP", "",
        *[f"- `{c}`" for c in sin_placsp[:20]],
    ]
    texto = "\n".join(lineas)
    ruta.write_text(texto, encoding="utf-8")
    obras.to_csv(ruta.with_name("obras.csv"), index=False)
    return texto


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--atom", nargs="*", default=[], help="ficheros ATOM locales (pruebas)")
    ap.add_argument("--excel", help="ruta del Excel de obras (sustituye a config)")
    ap.add_argument("--sin-excel", action="store_true")
    ap.add_argument("--desde", help="carga histórica desde AAAA o AAAAMM (p. ej. 2012)")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    con = db.conectar(cfg["base_datos"])
    carga_id = con.execute("INSERT INTO cargas (inicio, estado) VALUES (?, 'en curso')",
                           (db.ahora(),)).lastrowid
    con.commit()

    try:
        # 1) Descargar todo ANTES de escribir: si algo falla, la base no se toca
        placsp = recoger_placsp(cfg, args.atom, args.desde)
        if not placsp:
            raise FuenteError("PLACSP no devolvió ninguna obra del Ayuntamiento: posible cambio de formato")

        excel = None
        aviso_excel = ""
        if not args.sin_excel:
            try:
                excel = leer_excel_obras(args.excel or cfg["excel_obras_ejecucion"]["origen"])
                print(f"Excel municipal: {len(excel)} obras")
            except FuenteError as e:
                aviso_excel = f"Excel no cargado: {e}"
                print("AVISO:", aviso_excel)

        # 2) Escribir en una sola transacción
        cuenta = {"nuevo": 0, "cambiado": 0, "igual": 0}
        with con:
            for clave, d in placsp.items():
                cuenta[db.guardar(con, "placsp", clave, d, carga_id)] += 1
            if excel is not None:
                for _, fila in excel.iterrows():
                    datos = {k: (None if pd.isna(v) else v) for k, v in fila.items() if k != "clave"}
                    db.guardar(con, "excel_obras", fila["clave"], datos, carga_id)

        texto = informe(con, Path(cfg["base_datos"]).with_name("informe_cruce.md"))
        cruzadas = con.execute("SELECT SUM(en_excel_ayto) FROM obras").fetchone()[0] or 0
        con.execute("UPDATE cargas SET fin=?, estado='ok', mensaje=?, n_placsp=?, n_excel=?, n_cruzadas=? "
                    "WHERE id=?", (db.ahora(), f"{cuenta} {aviso_excel}".strip(), len(placsp),
                                   0 if excel is None else len(excel), cruzadas, carga_id))
        con.commit()
        print(f"Cambios PLACSP: {cuenta}")
        print(texto)
        return 0

    except FuenteError as e:
        con.rollback()
        con.execute("UPDATE cargas SET fin=?, estado='error', mensaje=? WHERE id=?",
                    (db.ahora(), str(e), carga_id))
        con.commit()
        print(f"ERROR: {e}\nLa base de datos no se ha modificado.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
