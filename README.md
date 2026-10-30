# Obras de Madrid

Web pública con las obras del Ayuntamiento de Madrid (en licitación, adjudicadas, en
ejecución y terminadas): qué se hace, dónde, cuánto cuesta, quién la hace y si cumple plazo.
Se actualiza sola cada noche con datos oficiales.

**Estado:** Fase 1 (datos) y Fase 2 (web) hechas, con carga histórica adelantada.
Pendiente de probar con datos reales.

## Dónde se ejecuta

- **Carga diaria:** GitHub Actions, cada noche (gratis en repositorios públicos).
- **Web:** GitHub Pages, estática, sin servidor.
- **Tu ordenador:** solo para probar y ajustar.

## Puesta en marcha (en tu ordenador)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q                 # pruebas con datos de muestra
```

1. Descarga el Excel «Obras en ejecución 2023-2027» de datos.madrid.es y guárdalo como
   `datos/obras_ejecucion.xlsx` (o pon su URL en `config.yaml → excel_obras_ejecucion.origen`).
2. Carga los datos y genera la web:

```bash
python cargar.py                    # carga diaria (feed actual + últimos 2 meses)
python cargar.py --desde 2023       # carga histórica (una vez; desde 2012 tarda horas)
python generar_web.py               # crea publicar/
python -m http.server -d publicar   # abre http://localhost:8000
```

3. Revisa `datos/informe_cruce.md`.
4. Completa `obras_conocidas.csv` con 20 obras que conozcas y ejecuta `python validar.py`.

### Ver la web con datos de ejemplo

```bash
python tests/crear_demo.py
python cargar.py --config tests/config_demo.yaml --atom tests/muestras/demo.atom
python generar_web.py --config tests/config_demo.yaml --salida datos_demo/publicar --aviso "Datos de ejemplo"
python -m http.server -d datos_demo/publicar
```

## Publicar en internet (una vez)

1. Crea un repositorio público en GitHub y sube esta carpeta.
2. Settings → Pages → Source: **GitHub Actions**.
3. Actions → «Carga diaria y web» → Run workflow. Para el histórico, escribe `2012` en «desde».

A partir de ahí se ejecuta sola cada noche. Si falla, la web sigue con los datos del día
anterior y GitHub te avisa por email.

## Piezas

| Fichero | Qué hace |
|---|---|
| `cargar.py` | Descarga PLACSP y el Excel municipal, cruza por expediente y guarda con histórico |
| `generar_web.py` | Crea `publicar/` (web + `data/obras.json` + `data/obras.csv`) |
| `obras/placsp.py` | Lectura del ATOM/CODICE de la PLACSP |
| `obras/excel_ayto.py` | Lectura del Excel municipal (columnas detectadas por palabras clave) |
| `obras/db.py` | SQLite: `registros`, `historial`, `cargas` y la vista `obras` |
| `obras/web.py` | Estado de la obra, ubicación y cálculos para la web |
| `sitio/index.html` | La web: mapa, lista, ficha, obras terminadas, cifras y glosario |

## Reglas que cumple

- **Solo fuentes oficiales.** Cada dato de la ficha indica su fuente, con enlace y fecha.
- **Neutralidad.** Solo datos y cálculos: baja, desviación de plazo, fin teórico.
- **Nada se borra.** Cada cambio de un expediente queda en `historial` y se ve en la ficha.
- **Terminada solo si una fuente lo dice.** Los contratos antiguos sin fecha de fin publicada
  se muestran aparte en «Obras terminadas», sin darlos por acabados.
- **Si una fuente falla**, no se escribe nada y la carga queda como `error`.

## Estado de cada obra

| Estado | Regla |
|---|---|
| En licitación | PLACSP: anuncio previo, publicada o en evaluación |
| Adjudicada | PLACSP: adjudicada o formalizada, sin dato de ejecución |
| En ejecución | El Excel municipal la da en ejecución |
| Terminada | El Excel municipal trae fecha de fin real o la da por finalizada |
| Anulada | PLACSP: anulada (oculta por defecto) |

## Pendiente de comprobar con datos reales

- Que los nombres de órgano del Ayuntamiento coinciden con el filtro de `config.yaml`.
- Que los expedientes de PLACSP y del Excel cruzan (la clave quita ceros a la izquierda).
- Nombres reales de columnas del Excel.
- Que la PLACSP publica zips anuales para años cerrados y mensuales para el año en curso.
- Ubicación: ahora es aproximada (centro del distrito). Siguiente paso: geocodificar las
  calles con el callejero del Geoportal.
