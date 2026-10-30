"""Pruebas automáticas: si la lógica de lectura o cruce se rompe, la carga diaria no se ejecuta."""
import sqlite3
import subprocess
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
MUESTRAS = RAIZ / "tests" / "muestras"
sys.path.insert(0, str(RAIZ))

from obras.placsp import clave_expediente, es_de_madrid, parsear_feed  # noqa: E402


def _config(tmp_path):
    cfg = yaml.safe_load((RAIZ / "tests" / "config_prueba.yaml").read_text())
    cfg["base_datos"] = str(tmp_path / "obras.sqlite")
    cfg["excel_obras_ejecucion"]["origen"] = str(MUESTRAS / "obras_ejecucion.xlsx")
    ruta = tmp_path / "config.yaml"
    ruta.write_text(yaml.safe_dump(cfg))
    return ruta, cfg["base_datos"]


def _cargar(config, *atoms):
    return subprocess.run([sys.executable, "cargar.py", "--config", str(config), "--atom",
                           *[str(MUESTRAS / a) for a in atoms]], cwd=RAIZ, capture_output=True, text=True)


def test_clave_expediente():
    assert clave_expediente("300/2025/00123") == clave_expediente("300/2025/123") == "300/2025/123"
    assert clave_expediente(" 300-2025-00123 ") == "300/2025/123"


def test_filtro_madrid():
    exps, borrados, _ = parsear_feed((MUESTRAS / "pagina1.atom").read_bytes())
    inc = ["ayuntamiento de madrid", "ciudad de madrid"]
    exc = ["comunidad de madrid"]
    obras_madrid = [e.expediente for e in exps if e.tipo_contrato == "3" and es_de_madrid(e, inc, exc)]
    assert obras_madrid == ["300/2025/00123", "300/2026/00456", "711/2026/01010"]


def test_carga_cruce_e_historial(tmp_path):
    config, bd = _config(tmp_path)
    r = _cargar(config, "pagina1.atom")
    assert r.returncode == 0, r.stderr
    r = _cargar(config, "pagina2.atom", "pagina1.atom")
    assert r.returncode == 0, r.stderr

    con = sqlite3.connect(bd)
    assert con.execute("SELECT COUNT(*), SUM(en_excel_ayto) FROM obras").fetchone() == (3, 2)
    assert con.execute("SELECT baja_pct FROM obras WHERE clave='300/2025/123'").fetchone()[0] == 17.5
    versiones = con.execute("SELECT COUNT(*) FROM historial WHERE clave='300/2026/456' AND fuente='placsp'"
                            ).fetchone()[0]
    assert versiones == 2  # adjudicada → resuelta, las dos guardadas


def test_fuente_rota_no_toca_la_base(tmp_path):
    config, bd = _config(tmp_path)
    assert _cargar(config, "pagina1.atom").returncode == 0
    roto = MUESTRAS / "_roto.atom"
    roto.write_text("<html>Servicio no disponible</html>")
    try:
        assert _cargar(config, "_roto.atom").returncode == 1
    finally:
        roto.unlink()
    con = sqlite3.connect(bd)
    assert con.execute("SELECT COUNT(*) FROM obras").fetchone()[0] == 3
    assert con.execute("SELECT estado FROM cargas ORDER BY id DESC LIMIT 1").fetchone()[0] == "error"
