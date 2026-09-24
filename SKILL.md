---
name: "analisis-tecnico-acciones"
description: "Genera un analisis tecnico grafico completo (SMA, RSI, MACD, volumen + OBV, Koncorde aproximado, soportes/resistencias, canales de tendencia, semaforo) de una accion en velas diarias o semanales, y lo publica como Artifact interactivo. Si el usuario no aclaro la temporalidad (diaria o semanal) al pedir el analisis, la skill pregunta antes de arrancar. Usar cuando el usuario pida analisis tecnico, grafico o semaforo de una accion/ticker (distinto del analisis fundamental+noticias de la skill 'analisis-de-acciones')."
---

# Analisis tecnico de acciones (grafico + semaforo)

Esta skill automatiza el analisis tecnico grafico de una accion (ticker o nombre de
empresa) siguiendo las reglas propias del usuario, validadas en detalle sobre KO y
MELI: velas semanales o diarias (segun lo que elija el usuario), SMA 20/50/200,
RSI(14), MACD(12,26,9), volumen (histograma + SMA20 de volumen + OBV), una reconstruccion aproximada del indicador Koncorde,
soportes/resistencias por giros significativos, el maximo historico (ATH), canales
de tendencia historicos, la estructura de los ultimos 2 anios (canal/triangulo/
rango), y una senal compuesta tipo semaforo (Venta fuerte / Venta / Neutral /
Compra / Compra fuerte). El resultado final es un Artifact HTML interactivo
(graficos sincronizados con TradingView Lightweight Charts) mas un informe
interpretativo en el chat.

Soporta dos temporalidades, semanal y diaria (ver paso 0).

Esta skill es DISTINTA de "analisis-de-acciones" (que hace un informe fundamental +
noticias + view de bancos). Si el usuario pide ambas cosas, se pueden combinar,
pero esta skill solo se ocupa de la parte grafica/tecnica.

## Cuando usarla

El usuario pide analizar tecnicamente una accion, ver su grafico, sus indicadores,
sus soportes/resistencias, sus canales de tendencia, o su semaforo/senal de
compra-venta. Puede dar un ticker (KO, MELI, AAPL) o el nombre de la empresa.

## Flujo de trabajo (paso a paso)

### 0. Definir la temporalidad (diaria o semanal)

Revisar si el usuario ya indico, en este mensaje o antes en la conversacion, si
quiere el analisis en velas **diarias** o **semanales**. Si no lo especifico,
preguntarselo explicitamente antes de seguir (con `AskUserQuestion` si esta
disponible, o como pregunta directa en el chat) — no asumir un default ni
arrancar a traer datos sin esto definido. Una vez definida, esta eleccion
(`INTERVAL` = `daily` o `weekly`) se usa en todo el resto del flujo: el
`interval` que se le pide a Twelve Data, el nombre de los archivos, el
parametro `--interval` de `analyze.py`, y el texto del reporte/artifact.

### 1. Resolver el ticker y traer datos con Twelve Data

Si el usuario dio un nombre de empresa en vez de ticker, usar
`mcp__Twelve_Data__search_symbol` para resolverlo.

Llamar:
- `mcp__Twelve_Data__get_quote(symbol=TICKER)` para precio actual, moneda,
  rango de 52 semanas.
- `mcp__Twelve_Data__get_time_series(symbol=TICKER, interval="1week" o "1day"
  segun `INTERVAL`, outputsize=5000)` para TODO el historico disponible (no
  usar Yahoo Finance/yfinance: el sandbox lo bloquea por allowlist de red;
  Alpha Vantage tiene un free tier demasiado limitado). Twelve Data es la unica
  fuente viable. Con `interval="1day"`, `outputsize=5000` cubre unos ~20 anios
  de ruedas; si el ticker tiene mas historico diario del que entra en 5000
  velas, esta bien — igual alcanza para todos los calculos de esta skill — pero
  se puede aclarar la limitacion si el usuario pregunta puntualmente por algo
  mas viejo.

El resultado de `get_time_series` suele ser grande y el harness lo guarda en un
archivo de texto plano (patron
`~/.claude/projects/.../tool-results/mcp-Twelve_Data-get_time_series-*.txt`,
JSON con forma `{"result": "texto-csv-con-punto-y-coma"}`). Extraerlo con Python
en vez de leerlo entero al contexto:

```python
import json
with open(RUTA_DEL_ARCHIVO) as f:
    data = json.load(f)
csv_text = data["result"]  # "datetime;open;high;low;close;volume\n..."
with open(f"{TICKER}_{INTERVAL}_raw.csv", "w") as f:
    f.write(csv_text)
```

Guardar el CSV crudo en el directorio de trabajo (scratchpad), p.ej.
`data/{TICKER}_{INTERVAL}_raw.csv` (`INTERVAL` = `daily` o `weekly`).

### 2. Usar los scripts desde la carpeta de la skill

Correr los scripts directamente desde la carpeta de la skill (`SKILL_DIR`, la
carpeta que contiene este SKILL.md): `scripts/analyze.py`, `scripts/gauge.py`,
`scripts/build_artifact.py` y `assets/template.html`. No copiarlos ni
reescribirlos; los datos y salidas van al directorio de trabajo.

### 3. Correr el pipeline

```bash
python3 {SKILL_DIR}/scripts/analyze.py --input data/{TICKER}_{INTERVAL}_raw.csv --ticker {TICKER} \
  --company "{NOMBRE COMPLETO DE LA EMPRESA}" --outdir out/{TICKER} --currency {MONEDA} \
  --interval {daily|weekly}
```

`--interval` es obligatorio y tiene que ser el mismo `INTERVAL` definido en el
paso 0 (y el mismo con el que se pidieron los datos en el paso 1).

Esto genera `out/{TICKER}/analysis.json`, `out/{TICKER}/chart_data.js` y
`out/{TICKER}/report.md`. La salida por stdout es un JSON corto
`{"ok": true, "signal": "...", "score": N}` — verificar que `ok` sea `true`.

Luego:

```bash
python3 {SKILL_DIR}/scripts/build_artifact.py --outdir out/{TICKER} --script-dir {SKILL_DIR}/assets
```

`--script-dir` apunta a `assets/` porque `build_artifact.py` lee `template.html` de esa carpeta.

Esto arma `out/{TICKER}/artifact.html` (HTML autocontenido, template + datos +
gauge). Verificar que no queden placeholders sin reemplazar:
`grep -c "__" out/{TICKER}/artifact.html` deberia dar 0.

### 4. Publicar el Artifact

Copiar el HTML final a `/mnt/user-data/outputs/{TICKER}_artifact.html`.
Publicar como Artifact (icon="chart"). Si ya se publicó en esta conversación, actualizar el mismo.

### 5. Presentar el resultado en el chat

Mostrar en el chat el contenido de `out/{TICKER}/report.md` (el informe
interpretativo: precio y estructura, medias moviles, RSI, MACD, volumen, Koncorde,
senal compuesta) y mencionar el veredicto del semaforo con su puntaje. No hace
falta pegar la URL del artifact (la tarjeta de publicacion ya la muestra).
Aclarar siempre que Koncorde es una reconstruccion propia/aproximada (no
oficial) y que el semaforo es una senal propia, no una recomendacion de
inversion.

## Notas de diseno

Ver `references/diseno.md` (leer solo para modificar los scripts).

## Dependencias de Python

`pandas`, `numpy`, `scipy` (para `scipy.signal.find_peaks`). Si no estan
instaladas: `pip install --break-system-packages pandas numpy scipy`.