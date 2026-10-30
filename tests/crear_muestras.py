"""Genera un ATOM y un Excel de muestra con la estructura real (CODICE) para las pruebas."""
from pathlib import Path
import pandas as pd

D = Path(__file__).parent / "muestras"

def entry(n, exp, titulo, organo, superiores, tipo, estado, presu, adj=None, empresa=None, upd="2026-10-20T10:00:00+02:00"):
    padres = ""
    for s in reversed(superiores):
        padres = f"<cac-place-ext:ParentLocatedParty><cac:PartyName><cbc:Name>{s}</cbc:Name></cac:PartyName>{padres}</cac-place-ext:ParentLocatedParty>"
    resultado = ""
    if adj:
        resultado = f"""<cac:TenderResult><cbc:ResultCode>8</cbc:ResultCode><cbc:AwardDate>2026-09-15</cbc:AwardDate>
          <cac:WinningParty><cac:PartyIdentification><cbc:ID schemeName="NIF">A00000000</cbc:ID></cac:PartyIdentification>
          <cac:PartyName><cbc:Name>{empresa}</cbc:Name></cac:PartyName></cac:WinningParty>
          <cac:AwardedTenderedProject><cac:LegalMonetaryTotal><cbc:TaxExclusiveAmount currencyID="EUR">{adj}</cbc:TaxExclusiveAmount>
          </cac:LegalMonetaryTotal></cac:AwardedTenderedProject></cac:TenderResult>"""
    return f"""<entry>
  <id>https://contrataciondelestado.es/sindicacion/licitacionesPerfilContratante/{n}</id>
  <link href="https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&amp;idEvl={n}"/>
  <summary type="text">Id licitación: {exp}</summary><title>{titulo}</title><updated>{upd}</updated>
  <cac-place-ext:ContractFolderStatus>
    <cbc:ContractFolderID>{exp}</cbc:ContractFolderID>
    <cbc-place-ext:ContractFolderStatusCode listURI="x">{estado}</cbc-place-ext:ContractFolderStatusCode>
    <cac-place-ext:LocatedContractingParty><cac:Party><cac:PartyName><cbc:Name>{organo}</cbc:Name></cac:PartyName></cac:Party>{padres}</cac-place-ext:LocatedContractingParty>
    <cac:ProcurementProject><cbc:Name>{titulo}</cbc:Name><cbc:TypeCode listURI="x">{tipo}</cbc:TypeCode>
      <cac:BudgetAmount><cbc:EstimatedOverallContractAmount currencyID="EUR">{presu}</cbc:EstimatedOverallContractAmount>
        <cbc:TotalAmount currencyID="EUR">{round(presu*1.21,2)}</cbc:TotalAmount><cbc:TaxExclusiveAmount currencyID="EUR">{presu}</cbc:TaxExclusiveAmount></cac:BudgetAmount>
      <cac:RequiredCommodityClassification><cbc:ItemClassificationCode listURI="x">45233000</cbc:ItemClassificationCode></cac:RequiredCommodityClassification>
      <cac:RealizedLocation><cbc:CountrySubentity>Madrid</cbc:CountrySubentity><cac:Address><cbc:CityName>Madrid</cbc:CityName></cac:Address></cac:RealizedLocation>
      <cac:PlannedPeriod><cbc:DurationMeasure unitCode="MON">18</cbc:DurationMeasure></cac:PlannedPeriod>
    </cac:ProcurementProject>{resultado}
  </cac-place-ext:ContractFolderStatus>
</entry>"""

CAB = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:at="http://purl.org/atompub/tombstones/1.0"
 xmlns:cac="urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2"
 xmlns:cbc="urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2"
 xmlns:cac-place-ext="urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2"
 xmlns:cbc-place-ext="urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2">
<title>Licitaciones</title><id>x</id><updated>2026-10-25T00:00:00+02:00</updated>
"""
JER = ["Madrid", "Ayuntamientos", "Comunidad de Madrid", "ENTIDADES LOCALES", "Sector Público"]  # como en la PLACSP real
entradas = [
    entry(1, "300/2025/00123", "Obras de soterramiento de la A-5 en el Paseo de Extremadura, tramo 1",
          "Área de Gobierno de Obras y Equipamientos", JER, "3", "RES", 100_000_000, 82_500_000, "UTE Ejemplo A5"),
    entry(2, "300/2026/00456", "Remodelación de la Plaza de España y entorno, fase final",
          "Junta de Gobierno de la Ciudad de Madrid", JER, "3", "ADJ", 5_000_000, 4_100_000, "Constructora Ejemplo SA"),
    entry(3, "300/2026/00789", "Servicio de limpieza de colegios", "Distrito de Centro", JER, "2", "PUB", 900_000),
    entry(4, "OB-12/2026", "Obras de urbanización calle Mayor", "Ayuntamiento de Getafe",
          ["Getafe", "Ayuntamientos", "Comunidad de Madrid", "ENTIDADES LOCALES", "Sector Público"], "3", "PUB", 1_200_000),
    entry(5, "2026/0099", "Obras de ampliación de la línea 11 de Metro",
          "Consejería de Transportes de la Comunidad de Madrid", ["Comunidad de Madrid"], "3", "PUB", 50_000_000),
    entry(6, "711/2026/01010", "Construcción de escuela infantil en el distrito de Vicálvaro",
          "Distrito de Vicálvaro", JER, "3", "PUB", 2_300_000),
    entry(7, "MJ-3/2026", "Pavimentación de calles", "Alcaldía del Ayuntamiento de Madridejos",
          ["Madridejos", "Ayuntamientos", "Toledo", "Castilla - La Mancha", "ENTIDADES LOCALES"], "3", "PUB", 300_000),
]
(D / "pagina1.atom").write_text(CAB + "\n".join(entradas) + "\n</feed>", encoding="utf-8")
# Segunda versión: el expediente 2 pasa a RES (cambio) → debe quedar en el histórico
e2 = entry(2, "300/2026/00456", "Remodelación de la Plaza de España y entorno, fase final",
           "Junta de Gobierno de la Ciudad de Madrid", JER, "3", "RES", 5_000_000, 4_100_000,
           "Constructora Ejemplo SA", upd="2026-10-25T09:00:00+02:00")
(D / "pagina2.atom").write_text(CAB + e2 + "\n<at:deleted-entry ref='x' when='2026-10-25T00:00:00+02:00'/></feed>", encoding="utf-8")

# Excel municipal con fila de título encima, como suele publicarse
filas = [
    ["OBRAS EN EJECUCIÓN 2023-2027", None, None, None, None, None, None, None],
    ["Nº Expediente", "Denominación", "Distrito", "Viales afectados", "Estado de la obra",
     "Empresa adjudicataria", "Fecha de inicio", "Fecha fin prevista"],
    ["300/2025/123", "Soterramiento A-5 tramo 1", "Latina", "Paseo de Extremadura", "En ejecución",
     "UTE Ejemplo A5", "2025-11-01", "2027-05-01"],
    ["300/2026/456", "Plaza de España fase final", "Centro", "Plaza de España", "En ejecución",
     "Constructora Ejemplo SA", "2026-10-01", "2027-04-01"],
    ["300/2024/999", "Obra adjudicada antes del periodo cargado", "Tetuán", "Calle Bravo Murillo",
     "En ejecución", "Otra SA", "2024-03-01", "2026-12-31"],
]
pd.DataFrame(filas).to_excel(D / "obras_ejecucion.xlsx", header=False, index=False)
print("Muestras creadas en", D)
