"""Datos de EJEMPLO (no reales) para ver la web antes de tener la carga real."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from crear_muestras import entry, CAB, JER, D

O = "Área de Gobierno de Obras y Equipamientos"
# (expediente, título, órgano, estado, licitación, adjudicación, empresa, fecha actualización)
demo = [
 ("300/2026/00811", "Renovación de aceras y calzada en la calle de Bravo Murillo (tramo Cuatro Caminos–Estrecho)", "Distrito de Tetuán", "PUB", 3_850_000, None, None, "2026-10-20"),
 ("300/2026/00790", "Construcción de un centro deportivo municipal en el barrio de Butarque, Villaverde", O, "EV", 11_200_000, None, None, "2026-10-12"),
 ("300/2026/00702", "Rehabilitación de la cubierta del mercado municipal de Moratalaz", "Distrito de Moratalaz", "PUB", 940_000, None, None, "2026-10-02"),
 ("300/2026/00455", "Remodelación de la plaza y el entorno del intercambiador de Aluche, Latina", O, "ADJ", 6_400_000, 5_312_000, "Construcciones Ejemplo Uno SA", "2026-09-28"),
 ("300/2025/00123", "Obras de soterramiento de la A-5 en el Paseo de Extremadura, tramo 1, Latina", O, "RES", 100_000_000, 82_500_000, "UTE Ejemplo A5", "2026-06-10"),
 ("300/2025/00610", "Nueva escuela infantil en el Ensanche de Vallecas, Villa de Vallecas", O, "RES", 2_900_000, 2_436_000, "Obras y Proyectos Ejemplo SL", "2025-12-01"),
 ("300/2025/00377", "Reforma integral del polideportivo de La Elipa, Ciudad Lineal", O, "RES", 4_200_000, 3_570_000, "Construcciones Ejemplo Uno SA", "2025-07-15"),
 ("300/2024/00918", "Ampliación de carril bici y reurbanización de la calle de Alcalá, San Blas-Canillejas", O, "RES", 5_600_000, 4_480_000, "Viales Ejemplo SA", "2024-11-20"),
 ("300/2024/00402", "Nuevo centro de mayores en el distrito de Usera", O, "RES", 3_100_000, 2_759_000, "Edificación Ejemplo SL", "2024-05-30"),
 ("300/2023/00733", "Reurbanización de la calle de Fuencarral, tramo sur, Centro", O, "RES", 7_900_000, 6_557_000, "Viales Ejemplo SA", "2023-10-05"),
 ("300/2023/00210", "Rehabilitación del Puente de los Franceses, Moncloa-Aravaca", O, "RES", 2_300_000, 2_001_000, "Puentes Ejemplo SA", "2023-03-14"),
 ("300/2021/00512", "Construcción del centro cultural de Valdebebas, Hortaleza", O, "RES", 8_700_000, 7_134_000, "Edificación Ejemplo SL", "2021-09-01"),
 ("300/2019/00330", "Remodelación del parque de Pradolongo, Usera", O, "RES", 1_950_000, 1_521_000, "Jardines Ejemplo SL", "2019-06-20"),
 ("300/2017/00145", "Ampliación del colegio público del barrio de Montecarmelo, Fuencarral-El Pardo", O, "RES", 2_650_000, 2_146_500, "Edificación Ejemplo SL", "2017-04-11"),
 ("300/2016/00088", "Reforma de la plaza del Dos de Mayo, Centro", O, "RES", 1_200_000, 948_000, "Viales Ejemplo SA", "2016-02-18"),
 ("300/2026/00120", "Obras de reparación de la pasarela de la avenida de la Paz", O, "ANUL", 600_000, None, None, "2026-04-02"),
]
xml = []
for i, (exp, t, org, est, lic, adj, emp, upd) in enumerate(demo, 100):
    e = entry(i, exp, t, org, JER, "3", est, lic, adj, emp, upd=upd + "T09:00:00+02:00")
    if adj:  # fecha de adjudicación coherente con la actualización
        e = e.replace("<cbc:AwardDate>2026-09-15</cbc:AwardDate>", f"<cbc:AwardDate>{upd}</cbc:AwardDate>")
    if exp == "300/2017/00145":
        e = e.replace('unitCode="MON">18<', 'unitCode="MON">14<')
    xml.append(e)
(D / "demo.atom").write_text(CAB + "\n".join(xml) + "\n</feed>", encoding="utf-8")

cab = ["Nº Expediente", "Denominación", "Distrito", "Viales afectados", "Estado de la obra",
       "Empresa adjudicataria", "Fecha de inicio", "Fecha fin prevista", "Fecha fin real", "Penalidades"]
filas = [
 ["300/2026/455", "Plaza de Aluche", "Latina", "Plaza de Aluche; calle de Illescas", "En ejecución", "Construcciones Ejemplo Uno SA", "2026-10-15", "2027-10-15", None, None],
 ["300/2025/123", "Soterramiento A-5 tramo 1", "Latina", "Paseo de Extremadura", "En ejecución", "UTE Ejemplo A5", "2025-11-01", "2027-05-01", None, None],
 ["300/2025/610", "Escuela infantil Ensanche de Vallecas", "Villa de Vallecas", "Calle de la Gavia", "En ejecución", "Obras y Proyectos Ejemplo SL", "2026-01-12", "2026-12-12", None, None],
 ["300/2025/377", "Polideportivo La Elipa", "Ciudad Lineal", "Calle del Doctor García Tapia", "Finalizada", "Construcciones Ejemplo Uno SA", "2025-09-01", "2026-06-30", "2026-09-14", "12.400 € por retraso"],
 ["300/2024/918", "Calle de Alcalá San Blas", "San Blas-Canillejas", "Calle de Alcalá (Canillejas–Torre Arias)", "Finalizada", "Viales Ejemplo SA", "2025-01-10", "2025-12-20", "2026-02-27", None],
 ["300/2024/402", "Centro de mayores Usera", "Usera", "Calle de Marcelo Usera", "Finalizada", "Edificación Ejemplo SL", "2024-07-01", "2025-07-01", "2025-06-18", None],
 ["300/2023/733", "Calle de Fuencarral tramo sur", "Centro", "Calle de Fuencarral (Gran Vía–Hortaleza)", "Finalizada", "Viales Ejemplo SA", "2023-11-06", "2024-09-30", "2024-12-20", "35.000 € por retraso"],
 ["300/2023/210", "Puente de los Franceses", "Moncloa-Aravaca", "Paseo de la Florida", "Finalizada", "Puentes Ejemplo SA", "2023-05-02", "2023-12-31", "2023-12-15", None],
 ["300/2022/815", "Asfaltado de calzadas en Barajas (operación asfalto 2023)", "Barajas", "Varias calles del distrito", "Finalizada", "Asfaltos Ejemplo SA", "2023-07-03", "2023-08-31", "2023-08-25", None],
]
pd.DataFrame([["RELACIÓN DE OBRAS EN EJECUCIÓN (EJEMPLO)"] + [None] * 9, cab] + filas).to_excel(
    D / "demo_obras.xlsx", header=False, index=False)
print("Demo creada")
