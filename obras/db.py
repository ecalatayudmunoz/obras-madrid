"""Base SQLite con histórico: nada se borra, cada cambio queda guardado."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS cargas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inicio TEXT NOT NULL, fin TEXT, estado TEXT, mensaje TEXT,
    n_placsp INTEGER, n_excel INTEGER, n_cruzadas INTEGER
);

-- Estado actual de cada registro, por fuente
CREATE TABLE IF NOT EXISTS registros (
    fuente TEXT NOT NULL,          -- 'placsp' | 'excel_obras'
    clave TEXT NOT NULL,           -- expediente normalizado
    datos TEXT NOT NULL,           -- JSON con los campos tal como vienen
    hash TEXT NOT NULL,
    primera_vez TEXT NOT NULL,     -- primera carga en que apareció
    ultima_vez TEXT NOT NULL,      -- última carga en que seguía publicado
    PRIMARY KEY (fuente, clave)
);

-- Cada versión distinta de un registro (incluida la primera)
CREATE TABLE IF NOT EXISTS historial (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente TEXT NOT NULL, clave TEXT NOT NULL,
    fecha TEXT NOT NULL, carga_id INTEGER, hash TEXT NOT NULL,
    datos TEXT NOT NULL, campos_cambiados TEXT
);
CREATE INDEX IF NOT EXISTS ix_hist ON historial(fuente, clave, fecha);
"""

VISTA = """
DROP VIEW IF EXISTS obras;
CREATE VIEW obras AS
SELECT
    p.clave,
    json_extract(p.datos, '$.expediente')                  AS expediente,
    json_extract(p.datos, '$.titulo')                      AS titulo,
    json_extract(p.datos, '$.estado')                      AS estado_contrato,
    json_extract(e.datos, '$.estado_obra')                 AS estado_obra,
    json_extract(p.datos, '$.organo')                      AS organo,
    json_extract(p.datos, '$.presupuesto_sin_iva')         AS presupuesto_licitacion,
    json_extract(p.datos, '$.importe_adjudicacion_sin_iva') AS importe_adjudicacion,
    CASE WHEN json_extract(p.datos, '$.presupuesto_sin_iva') > 0
              AND json_extract(p.datos, '$.importe_adjudicacion_sin_iva') IS NOT NULL
         THEN ROUND(100.0 * (1 - json_extract(p.datos, '$.importe_adjudicacion_sin_iva')
                              / json_extract(p.datos, '$.presupuesto_sin_iva')), 2) END AS baja_pct,
    COALESCE(json_extract(p.datos, '$.adjudicataria'), json_extract(e.datos, '$.empresa')) AS empresa,
    json_extract(p.datos, '$.plazo_valor')                 AS plazo,
    json_extract(p.datos, '$.plazo_unidad')                AS plazo_unidad,
    json_extract(e.datos, '$.distrito')                    AS distrito,
    json_extract(e.datos, '$.viales')                      AS viales,
    json_extract(e.datos, '$.fecha_inicio')                AS fecha_inicio,
    json_extract(e.datos, '$.fecha_fin_prevista')          AS fecha_fin_prevista,
    json_extract(e.datos, '$.fecha_fin_real')              AS fecha_fin_real,
    json_extract(e.datos, '$.penalidades')                 AS penalidades,
    json_extract(p.datos, '$.url_fuente')                  AS url_placsp,
    json_extract(p.datos, '$.actualizado_fuente')          AS actualizado_placsp,
    e.clave IS NOT NULL                                    AS en_excel_ayto
FROM registros p
LEFT JOIN registros e ON e.fuente = 'excel_obras' AND e.clave = p.clave
WHERE p.fuente = 'placsp';
"""


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conectar(ruta: str) -> sqlite3.Connection:
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta)
    con.executescript(ESQUEMA)
    con.executescript(VISTA)
    return con


def _hash(datos: dict) -> str:
    return hashlib.sha256(json.dumps(datos, sort_keys=True, ensure_ascii=False,
                                     default=str).encode()).hexdigest()[:16]


def guardar(con: sqlite3.Connection, fuente: str, clave: str, datos: dict, carga_id: int) -> str:
    """Inserta o actualiza. Devuelve 'nuevo', 'cambiado' o 'igual'."""
    h = _hash(datos)
    ts = ahora()
    fila = con.execute("SELECT hash, datos FROM registros WHERE fuente=? AND clave=?",
                       (fuente, clave)).fetchone()
    js = json.dumps(datos, ensure_ascii=False, default=str)
    if fila is None:
        con.execute("INSERT INTO registros VALUES (?,?,?,?,?,?)", (fuente, clave, js, h, ts, ts))
        con.execute("INSERT INTO historial (fuente, clave, fecha, carga_id, hash, datos, campos_cambiados) VALUES (?,?,?,?,?,?,?)",
                    (fuente, clave, ts, carga_id, h, js, None))
        return "nuevo"
    if fila[0] == h:
        con.execute("UPDATE registros SET ultima_vez=? WHERE fuente=? AND clave=?", (ts, fuente, clave))
        return "igual"
    antes = json.loads(fila[1])
    cambiados = sorted(k for k in set(antes) | set(datos) if antes.get(k) != datos.get(k))
    con.execute("UPDATE registros SET datos=?, hash=?, ultima_vez=? WHERE fuente=? AND clave=?",
                (js, h, ts, fuente, clave))
    con.execute("INSERT INTO historial (fuente, clave, fecha, carga_id, hash, datos, campos_cambiados) VALUES (?,?,?,?,?,?,?)",
                (fuente, clave, ts, carga_id, h, js, ",".join(cambiados)))
    return "cambiado"
