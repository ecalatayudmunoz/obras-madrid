"""Lectura del ATOM de la Plataforma de Contratación del Sector Público (formato CODICE).

Cada <entry> del feed es un expediente. Aquí se extraen los campos que necesita la web
y se conserva el enlace oficial a la ficha del expediente.
"""
from __future__ import annotations

import io
import re
import tempfile
import time
import unicodedata
import zipfile
from dataclasses import dataclass, asdict, field
from datetime import date
from typing import Iterator, Optional

import requests
from lxml import etree

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "at": "http://purl.org/atompub/tombstones/1.0",
    "cac": "urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2",
    "cac-place-ext": "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2",
    "cbc-place-ext": "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2",
}

# Estados CODICE del expediente → estado legible en la web
ESTADOS = {
    "PRE": "anuncio previo",
    "PUB": "en licitación",
    "EV": "en evaluación",
    "ADJ": "adjudicada",
    "RES": "resuelta",          # adjudicación formalizada / resuelta
    "ANUL": "anulada",
}

TIPOS_CONTRATO = {"1": "Suministros", "2": "Servicios", "3": "Obras", "21": "Gestión de servicios públicos",
                  "31": "Concesión de obras", "40": "Colaboración público-privada", "7": "Administrativo especial",
                  "8": "Privado", "50": "Patrimonial"}

HEADERS = {"User-Agent": "ObrasDeMadrid/0.1 (proyecto de transparencia; datos abiertos)"}


class FuenteError(RuntimeError):
    """La fuente no responde o cambió de formato. La carga se detiene sin tocar la base."""


@dataclass
class Expediente:
    entry_id: str
    expediente: str
    titulo: str
    estado_codigo: str
    estado: str
    tipo_contrato: str
    organo: str
    organos_superiores: list[str] = field(default_factory=list)
    presupuesto_sin_iva: Optional[float] = None
    presupuesto_con_iva: Optional[float] = None
    importe_adjudicacion_sin_iva: Optional[float] = None
    adjudicataria: Optional[str] = None
    adjudicataria_nif: Optional[str] = None
    fecha_adjudicacion: Optional[str] = None
    plazo_valor: Optional[float] = None
    plazo_unidad: Optional[str] = None
    lugar_ejecucion: Optional[str] = None
    cpv: list[str] = field(default_factory=list)
    url_fuente: Optional[str] = None
    actualizado_fuente: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["organos_superiores"] = " > ".join(self.organos_superiores)
        d["cpv"] = ",".join(self.cpv)
        return d


def normalizar(texto: str | None) -> str:
    """Minúsculas, sin tildes ni espacios repetidos (para comparar nombres)."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().lower()


def clave_expediente(exp: str | None) -> str:
    """Clave para cruzar fuentes: '300/2025/00123' y '300/2025/123' → '300/2025/123'."""
    if not exp:
        return ""
    partes = re.findall(r"[A-Za-z0-9]+", exp.upper())
    return "/".join(p.lstrip("0") or "0" if p.isdigit() else p for p in partes)


def _txt(el, path: str) -> Optional[str]:
    r = el.find(path, NS)
    return r.text.strip() if r is not None and r.text else None


def _num(el, path: str) -> Optional[float]:
    v = _txt(el, path)
    try:
        return float(v) if v is not None else None
    except ValueError:
        return None


def parsear_entry(entry) -> Optional[Expediente]:
    cfs = entry.find("cac-place-ext:ContractFolderStatus", NS)
    if cfs is None:
        return None

    lcp = cfs.find("cac-place-ext:LocatedContractingParty", NS)
    organo = _txt(lcp, "cac:Party/cac:PartyName/cbc:Name") if lcp is not None else None
    superiores: list[str] = []
    if lcp is not None:
        nodo = lcp.find("cac-place-ext:ParentLocatedParty", NS)
        while nodo is not None:
            n = _txt(nodo, "cac:PartyName/cbc:Name")
            if n:
                superiores.append(n)
            nodo = nodo.find("cac-place-ext:ParentLocatedParty", NS)

    pp = cfs.find("cac:ProcurementProject", NS)
    estado_cod = _txt(cfs, "cbc-place-ext:ContractFolderStatusCode") or ""

    # Puede haber varios resultados (lotes). Fase 1: se toma el primero y se suman importes.
    adjudicataria = nif = fecha_adj = None
    importe_adj = None
    for tr in cfs.findall("cac:TenderResult", NS):
        adjudicataria = adjudicataria or _txt(tr, "cac:WinningParty/cac:PartyName/cbc:Name")
        nif = nif or _txt(tr, "cac:WinningParty/cac:PartyIdentification/cbc:ID")
        fecha_adj = fecha_adj or _txt(tr, "cbc:AwardDate")
        imp = _num(tr, "cac:AwardedTenderedProject/cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount")
        if imp is not None:
            importe_adj = (importe_adj or 0) + imp

    link = entry.find("atom:link", NS)
    plazo_el = pp.find("cac:PlannedPeriod/cbc:DurationMeasure", NS) if pp is not None else None

    return Expediente(
        entry_id=_txt(entry, "atom:id") or "",
        expediente=_txt(cfs, "cbc:ContractFolderID") or "",
        titulo=(_txt(pp, "cbc:Name") if pp is not None else None) or _txt(entry, "atom:title") or "",
        estado_codigo=estado_cod,
        estado=ESTADOS.get(estado_cod, estado_cod.lower()),
        tipo_contrato=(_txt(pp, "cbc:TypeCode") if pp is not None else None) or "",
        organo=organo or "",
        organos_superiores=superiores,
        presupuesto_sin_iva=_num(pp, "cac:BudgetAmount/cbc:TaxExclusiveAmount") if pp is not None else None,
        presupuesto_con_iva=_num(pp, "cac:BudgetAmount/cbc:TotalAmount") if pp is not None else None,
        importe_adjudicacion_sin_iva=importe_adj,
        adjudicataria=adjudicataria,
        adjudicataria_nif=nif,
        fecha_adjudicacion=fecha_adj,
        plazo_valor=float(plazo_el.text) if plazo_el is not None and plazo_el.text else None,
        plazo_unidad=plazo_el.get("unitCode") if plazo_el is not None else None,
        lugar_ejecucion=" · ".join(filter(None, [
            _txt(pp, "cac:RealizedLocation/cbc:CountrySubentity") if pp is not None else None,
            _txt(pp, "cac:RealizedLocation/cac:Address/cbc:CityName") if pp is not None else None,
        ])) or None,
        cpv=[c.text for c in pp.findall("cac:RequiredCommodityClassification/cbc:ItemClassificationCode", NS)
             if c.text] if pp is not None else [],
        url_fuente=link.get("href") if link is not None else None,
        actualizado_fuente=_txt(entry, "atom:updated"),
    )


def parsear_feed(xml_bytes: bytes) -> tuple[list[Expediente], list[str], Optional[str]]:
    """Devuelve (expedientes, ids borrados, url de la página siguiente)."""
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as e:
        raise FuenteError(f"El ATOM no es XML válido: {e}") from e
    if root.tag != f"{{{NS['atom']}}}feed":
        raise FuenteError(f"Formato inesperado: raíz {root.tag}")

    exps = [x for x in (parsear_entry(e) for e in root.findall("atom:entry", NS)) if x]
    borrados = [d.get("ref") for d in root.findall("at:deleted-entry", NS)]
    sig = root.find("atom:link[@rel='next']", NS)
    return exps, borrados, sig.get("href") if sig is not None else None


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _descargar(url: str, destino, limite_s: int) -> int:
    """Descarga por trozos con un tiempo máximo TOTAL (requests solo limita cada lectura)."""
    inicio, total, aviso = time.monotonic(), 0, 0
    try:
        with requests.get(url, headers=HEADERS, timeout=(20, 60), stream=True) as r:
            r.raise_for_status()
            for trozo in r.iter_content(1 << 20):
                destino.write(trozo)
                total += len(trozo)
                t = time.monotonic() - inicio
                if t > limite_s:
                    raise FuenteError(f"{url} tarda más de {limite_s} s ({total >> 20} MB descargados)")
                if total >> 20 >= aviso + 50:
                    aviso = total >> 20
                    log(f"   … {aviso} MB en {t:.0f} s")
    except requests.RequestException as e:
        raise FuenteError(f"No responde {url}: {e}") from e
    return total


def _get(url: str, limite_s: int = 180) -> bytes:
    buf = io.BytesIO()
    _descargar(url, buf, limite_s)
    return buf.getvalue()


def leer_feed_paginado(url: str, max_paginas: int = 0) -> Iterator[Expediente]:
    """Recorre el feed siguiendo rel='next' (la Plataforma pagina de 500 en 500)."""
    n = 0
    while url:
        t = time.monotonic()
        datos = _get(url)
        exps, _, url = parsear_feed(datos)
        n += 1
        fechas = [e.actualizado_fuente for e in exps if e.actualizado_fuente]
        log(f"Feed página {n}: {len(exps)} entradas, {len(datos) >> 10} KB, {time.monotonic() - t:.1f} s"
            + (f" (hasta {min(fechas)[:10]})" if fechas else ""))
        yield from exps
        if max_paginas and n >= max_paginas:
            break


def leer_zip_mensual(url: str, limite_s: int = 1800) -> Iterator[Expediente]:
    """Descarga un zip (mensual o anual) a disco, no a memoria: los anuales pesan cientos de MB."""
    log(f"Descargando {url.rsplit('/', 1)[-1]}")
    with tempfile.TemporaryFile() as tmp:
        t = time.monotonic()
        mb = _descargar(url, tmp, limite_s) >> 20
        log(f"   {mb} MB en {time.monotonic() - t:.0f} s")
        try:
            z = zipfile.ZipFile(tmp)
        except zipfile.BadZipFile as e:
            raise FuenteError(f"{url} no es un zip válido") from e
        atoms = sorted(n for n in z.namelist() if n.endswith(".atom"))
        for i, nombre in enumerate(atoms, 1):
            exps, _, _ = parsear_feed(z.read(nombre))
            if i % 20 == 0 or i == len(atoms):
                log(f"   leídos {i}/{len(atoms)} ficheros del zip")
            yield from exps


def periodos_desde(desde: str, hoy: Optional[date] = None) -> list[str]:
    """Periodos a descargar desde 'AAAA' o 'AAAAMM' hasta el mes pasado.

    La PLACSP publica un zip por año para los años cerrados y uno por mes para el año
    en curso: 2012..2025 → '2012', ..., '2025'; 2026 → '202601', ..., mes anterior.
    """
    hoy = hoy or date.today()
    anio = int(desde[:4])
    mes = int(desde[4:6]) if len(desde) == 6 else 1
    out: list[str] = []
    while anio < hoy.year:
        if mes == 1:
            out.append(f"{anio}")
        else:  # empieza a mitad de un año cerrado: meses sueltos de ese año
            out += [f"{anio}{m:02d}" for m in range(mes, 13)]
        anio, mes = anio + 1, 1
    out += [f"{anio}{m:02d}" for m in range(mes, hoy.month)]
    return out


def es_de_madrid(exp: Expediente, incluir: list[str], excluir: list[str]) -> bool:
    """El contrato es del Ayuntamiento de Madrid.

    En la PLACSP la jerarquía es: órgano > Madrid > Ayuntamientos > Comunidad de Madrid > ...
    Se acepta si el municipio de la jerarquía es exactamente «Madrid», o si el nombre del
    órgano contiene un patrón de `incluir` como palabras completas (así «Madridejos» no entra).
    Se excluye si el propio órgano es de otra administración (p. ej. la Comunidad de Madrid).
    """
    organo = normalizar(exp.organo)
    if any(re.search(rf"\b{re.escape(p)}\b", organo) for p in excluir):
        return False
    sup = [normalizar(n) for n in exp.organos_superiores]
    for a, b in zip(sup, sup[1:]):
        if a == "madrid" and b == "ayuntamientos":
            return True
    return any(re.search(rf"\b{re.escape(p)}\b", n) for n in [organo, *sup] for p in incluir)
