"""Prepara los datos de la web a partir de la base: estado legible, ubicación y cálculos.

Reglas de neutralidad: solo se muestran datos de las fuentes y diferencias calculadas.
Si ninguna fuente dice que una obra está terminada, no se marca como terminada.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from .placsp import normalizar

# Centro aproximado de cada distrito (zona urbana). Se usa cuando la fuente solo da el distrito.
DISTRITOS = {
    "Centro": (40.4155, -3.7074), "Arganzuela": (40.3980, -3.6950), "Retiro": (40.4110, -3.6760),
    "Salamanca": (40.4300, -3.6770), "Chamartín": (40.4580, -3.6770), "Tetuán": (40.4600, -3.6990),
    "Chamberí": (40.4340, -3.7040), "Fuencarral-El Pardo": (40.4900, -3.7100),
    "Moncloa-Aravaca": (40.4350, -3.7400), "Latina": (40.3960, -3.7520),
    "Carabanchel": (40.3820, -3.7380), "Usera": (40.3830, -3.7060),
    "Puente de Vallecas": (40.3910, -3.6640), "Moratalaz": (40.4070, -3.6440),
    "Ciudad Lineal": (40.4440, -3.6520), "Hortaleza": (40.4720, -3.6420),
    "Villaverde": (40.3460, -3.7000), "Villa de Vallecas": (40.3720, -3.6200),
    "Vicálvaro": (40.4040, -3.6050), "San Blas-Canillejas": (40.4300, -3.6100),
    "Barajas": (40.4730, -3.5800),
}
_DIST_NORM = {normalizar(k): k for k in DISTRITOS}
# Variantes habituales en los textos
_DIST_NORM.update({"fuencarral": "Fuencarral-El Pardo", "moncloa": "Moncloa-Aravaca",
                   "san blas": "San Blas-Canillejas", "chamartin": "Chamartín"})

TERMINADA = ("finaliz", "terminad", "recibid", "recepcion", "concluid", "acabad")
EN_EJECUCION = ("ejecuc", "en obra", "iniciad", "en curso")


def distrito_de(*textos: Optional[str]) -> Optional[str]:
    for t in textos:
        n = normalizar(t)
        if not n:
            continue
        # el nombre más largo primero ("villa de vallecas" antes que "vallecas")
        for clave in sorted(_DIST_NORM, key=len, reverse=True):
            if clave in n:
                return _DIST_NORM[clave]
    return None


def _fecha(v) -> Optional[date]:
    if not v:
        return None
    s = str(v)[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _sumar_plazo(inicio: Optional[date], valor, unidad) -> Optional[date]:
    if not inicio or not valor:
        return None
    v = float(valor)
    dias = {"DAY": v, "WEE": v * 7, "MON": v * 30.44, "ANN": v * 365.25}.get(unidad or "")
    return inicio + timedelta(days=round(dias)) if dias else None


def estado_web(estado_codigo: Optional[str], estado_obra: Optional[str], fin_real) -> str:
    eo = normalizar(estado_obra)
    if estado_codigo == "ANUL":
        return "anulada"
    if fin_real or any(p in eo for p in TERMINADA):
        return "terminada"
    if any(p in eo for p in EN_EJECUCION):
        return "en ejecución"
    if estado_codigo in ("PRE", "PUB", "EV"):
        return "en licitación"
    return "adjudicada"


def _posicion(clave: str, distrito: Optional[str]):
    """Centro del distrito con un desplazamiento fijo (hasta ~600 m) para no apilar marcadores."""
    if distrito not in DISTRITOS:
        return None, None
    lat, lon = DISTRITOS[distrito]
    h = int(hashlib.md5(clave.encode()).hexdigest()[:8], 16)
    ang, r = (h % 360) * math.pi / 180, 0.002 + (h // 360 % 100) / 100 * 0.0035
    return round(lat + r * math.sin(ang), 5), round(lon + r * math.cos(ang) * 1.3, 5)


def _num(v) -> Optional[float]:
    try:
        return round(float(v), 2) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def construir(con: sqlite3.Connection) -> list[dict]:
    con.row_factory = sqlite3.Row
    reg = {(r["fuente"], r["clave"]): json.loads(r["datos"])
           for r in con.execute("SELECT fuente, clave, datos FROM registros")}
    hist: dict[str, list] = {}
    for r in con.execute("SELECT fuente, clave, fecha, campos_cambiados FROM historial ORDER BY fecha"):
        hist.setdefault(r["clave"], []).append(
            {"fecha": r["fecha"][:10], "fuente": r["fuente"],
             "cambios": r["campos_cambiados"].split(",") if r["campos_cambiados"] else None})

    claves = sorted({c for _, c in reg})
    obras = []
    for clave in claves:
        p = reg.get(("placsp", clave)) or {}
        e = reg.get(("excel_obras", clave)) or {}

        titulo = p.get("titulo") or e.get("denominacion") or ""
        distrito = distrito_de(e.get("distrito"), e.get("viales"), titulo, p.get("organo"))
        lat, lon = _posicion(clave, distrito)
        f_adj = _fecha(p.get("fecha_adjudicacion"))
        f_ini = _fecha(e.get("fecha_inicio"))
        f_prev = _fecha(e.get("fecha_fin_prevista"))
        f_real = _fecha(e.get("fecha_fin_real"))
        fin_teorico = _sumar_plazo(f_ini or f_adj, p.get("plazo_valor"), p.get("plazo_unidad"))
        lic, adj = _num(p.get("presupuesto_sin_iva")), _num(p.get("importe_adjudicacion_sin_iva") or
                                                             e.get("importe_adjudicacion"))
        fuentes = []
        if p:
            fuentes.append({"nombre": "Plataforma de Contratación del Sector Público",
                            "url": p.get("url_fuente"), "fecha": (p.get("actualizado_fuente") or "")[:10]})
        if e:
            fuentes.append({"nombre": "Ayuntamiento de Madrid · Obras en ejecución 2023-2027",
                            "url": "https://datos.madrid.es", "fecha": None})

        obras.append({
            "id": clave,
            "expediente": p.get("expediente") or e.get("expediente"),
            "titulo": titulo,
            "estado": estado_web(p.get("estado_codigo"), e.get("estado_obra"), f_real),
            "estado_contrato": p.get("estado"),
            "estado_obra": e.get("estado_obra"),
            "paga": "Ayuntamiento de Madrid",
            "organo": p.get("organo"),
            "distrito": distrito,
            "viales": e.get("viales"),
            "lat": lat, "lon": lon,
            "ubicacion": "aproximada" if lat else "sin ubicación",
            "empresa": p.get("adjudicataria") or e.get("empresa"),
            "licitacion": lic,
            "adjudicacion": adj,
            "baja_pct": round(100 * (1 - adj / lic), 2) if lic and adj else None,
            "plazo": p.get("plazo_valor"), "plazo_unidad": p.get("plazo_unidad"),
            "fecha_adjudicacion": f_adj.isoformat() if f_adj else None,
            "fecha_inicio": f_ini.isoformat() if f_ini else None,
            "fin_previsto": f_prev.isoformat() if f_prev else None,
            "fin_teorico": fin_teorico.isoformat() if fin_teorico else None,
            "fin_real": f_real.isoformat() if f_real else None,
            "desviacion_dias": (f_real - f_prev).days if f_real and f_prev else None,
            "penalidades": e.get("penalidades"),
            "anio": (f_adj or f_ini or _fecha(p.get("actualizado_fuente")) or date.today()).year,
            "fuentes": fuentes,
            "historial": hist.get(clave, []),
        })
    return obras
