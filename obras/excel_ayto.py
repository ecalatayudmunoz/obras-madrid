"""Lectura del Excel municipal «Obras en ejecución 2023-2027».

El Ayuntamiento cambia a veces el nombre de las columnas, así que se buscan por
palabras clave. Si falta la columna del expediente se considera cambio de formato.
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import requests

from .placsp import FuenteError, clave_expediente, normalizar, HEADERS

# campo interno → palabras que puede llevar el encabezado (sin tildes, minúsculas)
COLUMNAS = {
    "expediente": ["expediente", "n. exp", "num exp"],
    "denominacion": ["denominacion", "titulo", "objeto", "nombre"],
    "distrito": ["distrito"],
    "viales": ["vial", "ubicacion", "direccion", "emplazamiento"],
    "estado_obra": ["estado", "situacion"],
    "empresa": ["empresa", "adjudicatari", "contratista"],
    "importe_adjudicacion": ["importe de adjudicacion", "presupuesto de adjudicacion", "importe adj", "adjudicacion"],
    "fecha_inicio": ["fecha de inicio", "inicio"],
    "fecha_fin_real": ["fin real", "finalizacion real", "recepcion"],
    "fecha_fin_prevista": ["fin prevista", "finalizacion prevista", "fecha prevista", "fecha de fin", "fin"],
    "plazo": ["plazo"],
    "penalidades": ["penalidad"],
}


def _mapear_columnas(cols: list[str]) -> dict[str, str]:
    norm = {c: normalizar(str(c)) for c in cols}
    usadas: set[str] = set()
    mapa: dict[str, str] = {}
    for campo, claves in COLUMNAS.items():
        for clave in claves:  # el orden de las claves marca la prioridad
            col = next((c for c, n in norm.items() if clave in n and c not in usadas), None)
            if col is not None:
                mapa[campo] = col
                usadas.add(col)
                break
    return mapa


def _buscar_cabecera(raw: pd.DataFrame) -> int:
    """Algunos Excel traen títulos encima de la tabla: busca la fila con 'expediente'."""
    for i in range(min(len(raw), 30)):
        if any("expediente" in normalizar(str(v)) for v in raw.iloc[i].values):
            return i
    raise FuenteError("El Excel de obras no tiene columna de expediente (¿cambió el formato?)")


def leer_excel_obras(origen: str) -> pd.DataFrame:
    if origen.startswith("http"):
        try:
            r = requests.get(origen, headers=HEADERS, timeout=120)
            r.raise_for_status()
        except requests.RequestException as e:
            raise FuenteError(f"No responde el Excel de obras: {e}") from e
        datos = io.BytesIO(r.content)
    else:
        if not Path(origen).exists():
            raise FuenteError(f"No existe el Excel de obras en {origen}")
        datos = origen

    hojas = pd.read_excel(datos, sheet_name=None, header=None, dtype=str)
    tablas = []
    for nombre, raw in hojas.items():
        try:
            fila = _buscar_cabecera(raw)
        except FuenteError:
            continue
        df = raw.iloc[fila + 1:].copy()
        df.columns = [str(c).strip() for c in raw.iloc[fila].values]
        mapa = _mapear_columnas(list(df.columns))
        df = df[list(mapa.values())].rename(columns={v: k for k, v in mapa.items()})
        df["hoja"] = nombre
        tablas.append(df)
    if not tablas:
        raise FuenteError("Ninguna hoja del Excel de obras tiene columna de expediente")

    df = pd.concat(tablas, ignore_index=True)
    df = df[df["expediente"].notna() & (df["expediente"].str.strip() != "")]
    df["clave"] = df["expediente"].map(clave_expediente)
    return df.reset_index(drop=True)
