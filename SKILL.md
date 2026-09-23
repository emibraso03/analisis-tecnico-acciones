---
name: "analisis-tecnico-acciones"
description: "Genera un analisis tecnico grafico completo (SMA, RSI, MACD, Koncorde aproximado, soportes/resistencias, canales de tendencia, semaforo) de una accion en velas diarias o semanales, y lo publica como Artifact interactivo. Si el usuario no aclaro la temporalidad (diaria o semanal) al pedir el analisis, la skill pregunta antes de arrancar. Usar cuando el usuario pida analisis tecnico, grafico o semaforo de una accion/ticker (distinto del analisis fundamental+noticias de la skill 'analisis-de-acciones')."
---

# Analisis tecnico de acciones (grafico + semaforo)

Esta skill automatiza el analisis tecnico grafico de una accion (ticker o nombre de
empresa) siguiendo las reglas propias del usuario, validadas en detalle sobre KO y
MELI: velas semanales o diarias (segun lo que elija el usuario), SMA 20/50/200,
RSI(14), MACD(12,26,9), una reconstruccion aproximada del indicador Koncorde,
soportes/resistencias por giros significativos, el maximo historico (ATH), canales
de tendencia historicos, la estructura de los ultimos 2 anios (canal/triangulo/
rango), y una senal compuesta tipo semaforo (Venta fuerte / Venta / Neutral /
Compra / Compra fuerte). El resultado final es un Artifact HTML interactivo
(graficos sincronizados con TradingView Lightweight Charts) mas un informe
interpretativo en el chat.

Esta skill soporta dos temporalidades: **semanal** (la validada originalmente) y
**diaria**. Si el usuario no especifico cual quiere al pedir el analisis (ni en
este mensaje ni antes en la conversacion), hay que preguntarselo explicitamente
antes de arrancar (ver paso 0 del flujo) — no asumir un default.

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

### 2. Escribir los scripts de la skill en el scratchpad

Escribir (con la herramienta Write) los 4 archivos de mas abajo tal cual estan,
sin modificarlos, dentro de una carpeta de trabajo (p.ej. `scripts/`):
`analyze.py`, `gauge.py`, `build_artifact.py`, `template.html`.

### 3. Correr el pipeline

```bash
python3 scripts/analyze.py --input data/{TICKER}_{INTERVAL}_raw.csv --ticker {TICKER} \
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
python3 scripts/build_artifact.py --outdir out/{TICKER} --script-dir scripts
```

Esto arma `out/{TICKER}/artifact.html` (HTML autocontenido, template + datos +
gauge). Verificar que no queden placeholders sin reemplazar:
`grep -c "__" out/{TICKER}/artifact.html` deberia dar 0.

### 4. Publicar el Artifact

Copiar el HTML final a `/mnt/user-data/outputs/{TICKER}_artifact.html` y publicarlo
con la herramienta Artifact (`icon="chart"`, sin pasar `favicon`). Si es una
actualizacion de un artifact ya publicado en esta conversacion, pasar el mismo
`url`; si el tool rechaza el publish pidiendo que se lea/mergee la version
"vista", seguir las instrucciones del error (leer el archivo que indica, y
publicar desde ese contenido en vez de reintentar el mismo tal cual).

### 5. Presentar el resultado en el chat

Mostrar en el chat el contenido de `out/{TICKER}/report.md` (el informe
interpretativo: precio y estructura, medias moviles, RSI, MACD, Koncorde,
senal compuesta) y mencionar el veredicto del semaforo con su puntaje. No hace
falta pegar la URL del artifact (la tarjeta de publicacion ya la muestra).
Aclarar siempre que Koncorde es una reconstruccion propia/aproximada (no
oficial) y que el semaforo es una senal propia, no una recomendacion de
inversion.

## Notas y decisiones de diseno (por que esta hecho asi)

- **Temporalidad diaria o semanal, a eleccion del usuario**: originalmente el
  usuario pidio velas japonesas semanales con historico completo. Ahora la
  skill soporta ambas temporalidades y pregunta cual usar si no se especifico
  (paso 0). Los periodos de los indicadores estandar (SMA 20/50/200, RSI 14,
  MACD 12/26/9, Koncorde m=15/win=90) se dejan con el mismo numero de velas en
  ambos casos — es la convencion habitual de analisis tecnico (p.ej. "SMA200"
  significa 200 ruedas, sea semana o dia; el famoso "200-day moving average"
  diario y el "SMA200 semanal" de largo plazo son ambos validos con esa misma
  logica). En cambio, los detectores basados en distancia/duracion en tiempo
  real (soportes/resistencias, canales de tendencia, giros mayores) SI se
  reescalan: se calcula `bars_per_week` (1 para semanal, 5 para diario, por
  las ruedas habiles de la semana) y los parametros que antes eran "N semanas"
  se multiplican por ese factor para conservar el mismo significado temporal
  sea cual sea la temporalidad. La extrapolacion de fechas futuras (canales,
  linea de ATH) tambien se generalizo: en vez de asumir un paso fijo de una
  semana por vela, se calcula el espaciado real mediano entre velas del propio
  dataframe y se usa ese valor para proyectar hacia adelante.
- **Rango por defecto del grafico**: en semanal el zoom inicial sigue siendo
  3 anios (boton "3A"); en diario arranca en 1 anio (boton "1A"), con un boton
  extra "6M" disponible en la barra de rangos para acercar mas si hace falta.
- **Fuente de datos**: Yahoo Finance/yfinance esta bloqueado por el allowlist
  de red del sandbox (403 Host not in allowlist). Alpha Vantage da solo 25
  llamadas/dia gratis. Twelve Data (800/dia gratis) es la fuente usada.
- **Soportes/resistencias**: NO se usa cada vela; se detectan giros
  significativos (`scipy.signal.find_peaks` sobre log-precio) con prominencia
  minima (6%), se agrupan en bins de precio (2%) y solo se muestran los que
  tienen al menos 3 toques Y fueron tocados en los ultimos `recent_years`
  (default 15) anios — para no ensuciar el grafico con niveles viejos
  irrelevantes, salvo que sigan vigentes.
- **Maximo historico (ATH)**: se calcula solo con apertura/cierre, nunca con
  mechas (maximos/minimos intradiarios), y la linea gruesa solo se extiende
  hacia adelante en el tiempo desde el punto del ATH, nunca hacia atras.
- **Canales de tendencia**: se detectan tramos historicos mayores (giros con
  prominencia 20%+, minimo 52 semanas) y para cada tramo se calcula el
  convex hull (algoritmo monotone chain propio) de los puntos apertura/cierre,
  tomando el borde mas largo de la mitad inferior (soporte) y superior
  (resistencia) del hull — no una regresion lineal, sino la envolvente real.
  Las lineas se extienden proporcionalmente hacia el futuro para que se vean
  mejor.
- **Estructura de los ultimos 2 anios**: a diferencia de los canales
  historicos, se calcula sobre MECHAS (hull inferior de los minimos para el
  soporte, hull superior de los maximos para la resistencia), porque las
  lineas tienen que contener las velas completas: con apertura/cierre el
  soporte quedaba tangente a los cuerpos y las mechas lo atravesaban. El
  patron se clasifica por la pendiente de ambas aristas (canal alcista/
  bajista, triangulo simetrico/ascendente/descendente, rango lateral). Si es
  canal, la linea opuesta NO es la arista independiente del hull sino una
  PARALELA a la linea de tendencia desplazada hasta la mecha mas extrema:
  en alcista se ancla el soporte (minimos) y la resistencia es paralela por
  el maximo mas alto; en bajista se ancla la resistencia (maximos) y el
  soporte es paralelo por el minimo mas bajo. Motivo: en una suba acelerada
  la arista superior del hull es la cuerda inicio->ATH y queda muy por
  encima de las velas recientes (caso GOOG, sep-2026). Triangulos y rango
  lateral mantienen las dos aristas independientes. Las lineas se extienden
  hasta el mismo horizonte futuro que la linea de ATH.
- **Regla del canal: TODAS las velas (con mechas) adentro.** Se valida
  numericamente (0 minimos por debajo del soporte y 0 maximos por encima de
  la resistencia desde el inicio del canal) Y se tiene que ver asi en el
  grafico. Para lo segundo, las rectas (canal de 2 anios, canales
  historicos) se emiten con UN PUNTO POR VELA (`_line_points`), incluidas
  las velas futuras sobre la grilla (ultimo dato + k * espaciado mediano).
  Motivo: Lightweight Charts tiene escala de tiempo por INDICE, no por
  fecha. Con solo 2 puntos, el extremo futuro (p.ej. 6 meses adelante)
  queda a UNA vela del ultimo dato: la extension se comprime, la recta se
  rota hacia arriba y atraviesa las velas aunque los numeros esten bien
  (bug detectado en GOOG, sep-2026). Nunca emitir puntos con fechas fuera
  de la grilla de velas (fechas interpoladas agregan slots extra y
  deforman el eje).
- **Koncorde aproximado**: NO es el indicador oficial de TradingView/Blai5
  (no hay forma de replicarlo exacto sin su codigo fuente). Es una
  reconstruccion propia a partir de la formula publica de 2008: PVI/NVI
  normalizados (linea azul = manos fuertes/institucional, verde = manos
  debiles/retail), y una linea marron de tendencia (RSI+MFI+oscilador de
  Bollinger+Estocastico sobre precio tipico) con su media de senal (roja).
  Las 3 capas de histograma se pintan SIEMPRE superpuestas con transparencia
  en el orden verde (atras) -> marron -> azul (adelante), sin filtrar
  condicionalmente ninguna.
- **Colores dependientes del tema**: las lineas de estructura/canales usan un
  color que cambia segun modo claro/oscuro (`#1a1a1a` claro / `#e8e8e8`
  oscuro) porque un color fijo oscuro se volvia invisible en modo oscuro.
- **`priceLineVisible:false, lastValueVisible:false`** en TODAS las series de
  linea: sin esto, Lightweight Charts dibuja automaticamente una linea
  punteada del ultimo valor que el usuario no queria ver.
- **Semaforo (senal compuesta)**: 9 votos (-1/0/+1) sobre precio vs SMA20/50/200,
  cruce SMA20 vs SMA50, zona de RSI, histograma y cruce de MACD, cruce y fuerza
  de Koncorde. Puntaje neto en [-9,+9] mapeado a 5 niveles (Venta fuerte <= -5,
  Venta <= -2, Neutral < 2, Compra < 5, Compra fuerte >= 5). Se muestra como un
  velocimetro SVG semicircular con 5 arcos de color + aguja + pill de color con
  el veredicto, replicando el diseno que el usuario referencio (rojo->gris->
  verde). Los labels de zona se muestran como una leyenda horizontal debajo del
  SVG (no como texto rotado dentro del SVG: eso generaba clipping).
- **CDN de graficos**: usar `https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js`.
  La misma libreria via cdnjs.cloudflare.com fallaba (pagina en blanco) en
  artifacts publicados; jsdelivr funciona.
- Probado de punta a punta con dos tickers de historiales muy distintos: KO
  (2960 semanas, desde 1969) y MELI (999 semanas, desde 2007) — ambos corren
  sin errores, sin NaN filtrandose al JS, y con SMA200/niveles/canales
  calculados correctamente pese a la diferencia de historial. Tambien probado
  de punta a punta en modo diario con series sinteticas (con y sin tendencia
  marcada): el pipeline corre sin errores en ambas temporalidades, sin
  placeholders sin reemplazar en el artifact, con el subtitulo/ARIA labels y
  el rango por defecto del grafico ajustandose correctamente segun
  `--interval`, y con soportes/canales/estructura detectados de forma
  razonable en diario cuando la serie tiene tendencias reales.

## scripts/analyze.py

```python
#!/usr/bin/env python3
"""
Analisis tecnico automatizado de una accion a partir de su historico semanal
(OHLCV) descargado de Twelve Data.

Calcula: SMA20/50/200, RSI14, MACD(12,26,9), una reconstruccion aproximada
del indicador Koncorde (PVI/NVI + RSI + MFI + Bollinger + Estocastico),
niveles de soporte/resistencia (giros significativos con prominencia minima
y vigencia reciente), canales de tendencia historicos (convex hull por
tramo), la estructura de los ultimos 2 anios, la linea de maximo historico,
y una senal compuesta tipo "semaforo" (venta fuerte / venta / neutral /
compra / compra fuerte) basada en 9 votos de los indicadores anteriores.

Uso:
  python3 analyze.py --input RAW.csv --ticker KO --company "The Coca-Cola Company" \
    --outdir OUT/ --interval weekly

RAW.csv: texto crudo devuelto por Twelve Data get_time_series (interval=1week o
1day, segun --interval), formato "datetime;open;high;low;close;volume" separado
por ';'.

--interval: "daily" o "weekly". Define, ademas del propio dataframe, cuantas
velas por semana tiene la serie (`bars_per_week`: 1 en semanal, 5 en diario) y
cuantas velas hay en un anio (`bars_per_year`: 52 en semanal, 252 en diario).
Estos dos numeros se usan para reescalar a "tiempo real" los parametros de
deteccion de giros/soportes/canales que antes asumian velas semanales.
"""
import argparse
import json
import numpy as np
import pandas as pd
from collections import defaultdict
from scipy.signal import find_peaks


# --------------------------------------------------------------------------
# Carga y limpieza
# --------------------------------------------------------------------------
def load_raw(path):
    with open(path) as f:
        text = f.read()
    lines = text.strip().split("\n")
    header = lines[0].split(";")
    rows = [l.split(";") for l in lines[1:]]
    df = pd.DataFrame(rows, columns=header)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.drop_duplicates(subset="datetime").sort_values("datetime").reset_index(drop=True)
    df = df[df["close"] > 0].reset_index(drop=True)
    return df


# --------------------------------------------------------------------------
# Indicadores estandar
# --------------------------------------------------------------------------
def add_smas(df):
    df["sma20"] = df["close"].rolling(20).mean()
    df["sma50"] = df["close"].rolling(50).mean()
    df["sma200"] = df["close"].rolling(200).mean()
    return df


def add_rsi(df, period=14):
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


def add_macd(df, fast=12, slow=26, signal=9):
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    return df


# --------------------------------------------------------------------------
# Koncorde aproximado (formula publica de Blai5, 2008 - reconstruccion propia)
# --------------------------------------------------------------------------
def add_koncorde(df, m=15, win=90):
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    tp = (high + low + close) / 3.0

    n = len(df)
    pvi = np.zeros(n)
    nvi = np.zeros(n)
    pvi[0] = 1000.0
    nvi[0] = 1000.0
    for i in range(1, n):
        price_chg = (close.iloc[i] - close.iloc[i - 1]) / close.iloc[i - 1] if close.iloc[i - 1] != 0 else 0
        pvi[i] = pvi[i - 1] + price_chg * pvi[i - 1] if volume.iloc[i] > volume.iloc[i - 1] else pvi[i - 1]
        nvi[i] = nvi[i - 1] + price_chg * nvi[i - 1] if volume.iloc[i] < volume.iloc[i - 1] else nvi[i - 1]

    df["pvi"] = pvi
    df["nvi"] = nvi
    df["pvim"] = df["pvi"].ewm(span=m, adjust=False).mean()
    df["nvim"] = df["nvi"].ewm(span=m, adjust=False).mean()

    pvimax = df["pvim"].rolling(win).max()
    pvimin = df["pvim"].rolling(win).min()
    nvimax = df["nvim"].rolling(win).max()
    nvimin = df["nvim"].rolling(win).min()

    df["oscp"] = (df["pvi"] - df["pvim"]) * 100 / (pvimax - pvimin).replace(0, np.nan)
    df["azul"] = (df["nvi"] - df["nvim"]) * 100 / (nvimax - nvimin).replace(0, np.nan)

    # RSI(14) y MFI(14) sobre TotalPrice
    delta = tp.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    xrsi = 100 - (100 / (1 + avg_gain / avg_loss))

    mf = tp * volume
    pos_mf = mf.where(tp > tp.shift(1), 0.0)
    neg_mf = mf.where(tp < tp.shift(1), 0.0)
    pos_sum = pos_mf.rolling(14).sum()
    neg_sum = neg_mf.rolling(14).sum()
    mfr = pos_sum / neg_sum.replace(0, np.nan)
    xmf = 100 - (100 / (1 + mfr))

    # Oscilador de Bollinger (25, 2)
    bb_mid = tp.rolling(25).mean()
    bb_std = tp.rolling(25).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    ob1 = (bb_upper + bb_lower) / 2
    ob2 = (bb_upper - bb_lower).replace(0, np.nan)
    boll_osc = ((tp - ob1) / ob2) * 100

    # Estocastico(21,3)
    hh21 = tp.rolling(21).max()
    ll21 = tp.rolling(21).min()
    raw_k = (tp - ll21) * 100 / (hh21 - ll21).replace(0, np.nan)
    stoc = raw_k.rolling(3).mean()

    df["marron"] = (xrsi + xmf + boll_osc + (stoc / 3)) / 2
    df["verde"] = df["marron"] + df["oscp"]
    df["media"] = df["marron"].ewm(span=m, adjust=False).mean()
    return df


# --------------------------------------------------------------------------
# Soportes y resistencias (giros significativos, prominencia + vigencia)
# --------------------------------------------------------------------------
def find_support_resistance(df, bars_per_week=1.0, prominence_pct=0.06, min_distance_weeks=6,
                             bin_pct=0.02, min_touch=3, recent_years=15):
    """min_distance_weeks se expresa en semanas y se convierte a velas con
    bars_per_week (1 en semanal, 5 en diario) para que el criterio de
    separacion minima entre giros signifique lo mismo en tiempo real sea cual
    sea la temporalidad de los datos."""
    close = df["close"].values
    logc = np.log(close)
    prom = np.log(1 + prominence_pct)
    min_distance = max(1, round(min_distance_weeks * bars_per_week))
    peaks, _ = find_peaks(logc, prominence=prom, distance=min_distance)
    troughs, _ = find_peaks(-logc, prominence=prom, distance=min_distance)
    idxs = np.concatenate([peaks, troughs])
    if len(idxs) == 0:
        return []
    prices = close[idxs]
    dates = df["datetime"].values[idxs]

    logp = np.log(prices)
    bin_width = np.log(1 + bin_pct)
    bins = np.arange(logp.min(), logp.max() + bin_width, bin_width)
    bin_idx = np.digitize(logp, bins)
    bt = defaultdict(list)
    for bi, p, d in zip(bin_idx, prices, dates):
        bt[bi].append((p, d))

    recent_cutoff = df["datetime"].max() - pd.DateOffset(years=recent_years)
    levels = []
    for bi, lst in bt.items():
        weeks = len(set([d for _, d in lst]))
        last = max([d for _, d in lst])
        if weeks >= min_touch and pd.Timestamp(last) >= recent_cutoff:
            levels.append({
                "price": round(float(np.median([p for p, _ in lst])), 2),
                "touches": weeks,
            })
    levels.sort(key=lambda x: x["price"])
    return levels


def find_ath(df):
    """Maximo historico usando solo cierre o apertura (nunca mechas)."""
    max_close_row = df.loc[df["close"].idxmax()]
    max_open_row = df.loc[df["open"].idxmax()]
    if max_open_row["open"] >= max_close_row["close"]:
        return float(max_open_row["open"]), max_open_row["datetime"]
    return float(max_close_row["close"]), max_close_row["datetime"]


# --------------------------------------------------------------------------
# Canales de tendencia (convex hull por tramo de giro mayor)
# --------------------------------------------------------------------------
def _convex_hull(points):
    points = sorted(set(points))
    if len(points) <= 1:
        return points, points

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1], upper[:-1][::-1]


def _longest_edge(hull_chain):
    if len(hull_chain) < 2:
        return None
    best, best_span = None, -1
    for i in range(len(hull_chain) - 1):
        x1, y1 = hull_chain[i]
        x2, y2 = hull_chain[i + 1]
        span = x2 - x1
        if span > best_span:
            best_span, best = span, (hull_chain[i], hull_chain[i + 1])
    return best


def _fit_trendlines(df, start_idx, end_idx):
    sub = df.iloc[start_idx:end_idx + 1]
    pts = []
    for i, (o, c) in zip(sub.index, zip(sub["open"], sub["close"])):
        pts.append((i, float(o)))
        pts.append((i, float(c)))
    lo, up = _convex_hull(pts)
    return _longest_edge(lo), _longest_edge(up)


def _median_bar_days(df):
    """Espaciado real (en dias de calendario) entre velas consecutivas,
    calculado del propio dataframe en vez de asumido fijo. En semanal da ~7;
    en diario da ~1-3 (por fines de semana/feriados). Se usa para proyectar
    fechas mas alla del ultimo dato sin hardcodear la temporalidad."""
    diffs = df["datetime"].diff().dropna().dt.days
    if len(diffs) == 0:
        return 7.0
    med = float(diffs.median())
    return med if med > 0 else 7.0


def _idx_to_date_str(df, i_float, bar_days=7.0):
    n = len(df)
    base_idx = int(np.floor(i_float))
    frac = i_float - base_idx
    if base_idx >= n - 1:
        base_date = df["datetime"].iloc[n - 1]
        extra_bars = i_float - (n - 1)
        d = base_date + pd.Timedelta(days=bar_days * extra_bars)
    else:
        d1 = df["datetime"].iloc[base_idx]
        d2 = df["datetime"].iloc[base_idx + 1]
        d = d1 + (d2 - d1) * frac
    return d.strftime("%Y-%m-%d")


def _extend_edge_proportional(edge, extra_frac=0.35):
    (i1, p1), (i2, p2) = edge
    span = i2 - i1
    extra = span * extra_frac
    slope = (p2 - p1) / span if span != 0 else 0
    return (i1, p1), (i2 + extra, p2 + slope * extra)


def _extend_edge_to_target(edge, target_idx):
    (i1, p1), (i2, p2) = edge
    span = i2 - i1
    slope = (p2 - p1) / span if span != 0 else 0
    return (i1, p1), (target_idx, p2 + slope * (target_idx - i2))


def _line_points(df, i1, v1, i2, v2, bar_days=7.0):
    """Muestrea la recta en CADA vela entera entre i1 e i2 (incluye velas
    futuras, espaciadas bar_days desde el ultimo dato). Lightweight Charts usa
    una escala de tiempo por INDICE, no por fecha: una serie de 2 puntos con
    el extremo en el futuro coloca ese punto a UNA sola vela del ultimo dato,
    comprimiendo la extension y rotando la recta hacia arriba (atraviesa
    velas). Tambien una fecha interpolada que no cae en la grilla agrega un
    slot extra. Emitir un punto por vela, sobre la grilla, evita las dos cosas."""
    slope = (v2 - v1) / (i2 - i1) if i2 != i1 else 0.0
    pts = []
    for k in range(int(np.ceil(i1)), int(np.floor(i2)) + 1):
        pts.append({"time": _idx_to_date_str(df, k, bar_days), "value": round(float(v1 + slope * (k - i1)), 2)})
    return pts


def find_major_legs(df, bars_per_week=1.0, prominence_pct=0.20, min_distance_weeks=10, min_weeks=52):
    """min_distance_weeks y min_weeks se expresan en semanas y se convierten a
    velas con bars_per_week, igual que en find_support_resistance, para que
    "un tramo mayor dura al menos 1 anio" siga significando lo mismo en
    diario que en semanal."""
    close = df["close"].values
    logc = np.log(close)
    prom = np.log(1 + prominence_pct)
    min_distance = max(1, round(min_distance_weeks * bars_per_week))
    min_bars = max(1, round(min_weeks * bars_per_week))
    peaks, _ = find_peaks(logc, prominence=prom, distance=min_distance)
    troughs, _ = find_peaks(-logc, prominence=prom, distance=min_distance)
    swings = sorted([(i, "high") for i in peaks] + [(i, "low") for i in troughs])
    legs = []
    for i in range(len(swings) - 1):
        idx1, _ = swings[i]
        idx2, _ = swings[i + 1]
        bars = idx2 - idx1
        if bars >= min_bars:
            legs.append((idx1, idx2))
    return legs


def historical_channels(df, legs, future_target_idx, bar_days=7.0):
    lines = []
    for i1, i2 in legs:
        s, r = _fit_trendlines(df, i1, i2)
        for edge in (s, r):
            if edge is None:
                continue
            ext = _extend_edge_proportional(edge)
            (a1, ap1), (a2, ap2) = ext
            lines.append({"width": 1, "data": _line_points(df, a1, ap1, a2, ap2, bar_days)})
    return lines


def _fit_wick_trendlines(df, start_idx, end_idx):
    """Igual que _fit_trendlines pero sobre mechas: convex hull inferior de los
    minimos (soporte) y superior de los maximos (resistencia). Se usa solo en
    la estructura reciente, donde las lineas tienen que CONTENER las velas
    completas (con mechas), no solo los cuerpos."""
    sub = df.iloc[start_idx:end_idx + 1]
    lo, _ = _convex_hull([(i, float(v)) for i, v in zip(sub.index, sub["low"])])
    _, up = _convex_hull([(i, float(v)) for i, v in zip(sub.index, sub["high"])])
    return _longest_edge(lo), _longest_edge(up)


def _parallel_edge(df, anchor, start_idx, end_idx, side):
    """Recta paralela a `anchor` desplazada hasta el extremo opuesto del rango:
    side="upper" -> pasa por el maximo (high) mas alejado por encima;
    side="lower" -> pasa por el minimo (low) mas alejado por debajo."""
    (i1, p1), (i2, p2) = anchor
    slope = (p2 - p1) / (i2 - i1) if i2 != i1 else 0.0
    sub = df.iloc[start_idx:end_idx + 1]
    base = p1 + slope * (sub.index.values - i1)
    if side == "upper":
        off = float((sub["high"].values - base).max())
    else:
        off = float((sub["low"].values - base).min())
    return (i1, p1 + off), (i2, p2 + off)


def _pct_slope_per_week(edge, bars_per_week):
    (i1, p1), (i2, p2) = edge
    span = i2 - i1
    raw = ((p2 - p1) / p1) / span * 100 if span != 0 else 0
    # "% por semana" para que los umbrales valgan en diario y en semanal
    return raw * bars_per_week


def recent_structure(df, years, future_target_idx, bar_days=7.0, bars_per_week=1.0):
    cutoff = df["datetime"].max() - pd.DateOffset(years=years)
    matches = df[df["datetime"] >= cutoff]
    if matches.empty:
        return [], "sin_datos"
    start_idx = matches.index[0]
    end_idx = len(df) - 1
    s, r = _fit_wick_trendlines(df, start_idx, end_idx)
    if s is None or r is None:
        return [], "indeterminado"

    s_slope = _pct_slope_per_week(s, bars_per_week)
    r_slope = _pct_slope_per_week(r, bars_per_week)
    if s_slope > 0.05 and r_slope < -0.05:
        pattern = "triangulo_simetrico"
    elif s_slope > 0.05 and abs(r_slope) <= 0.05:
        pattern = "triangulo_ascendente"
    elif abs(s_slope) <= 0.05 and r_slope < -0.05:
        pattern = "triangulo_descendente"
    elif s_slope > 0.05 and r_slope > 0.05:
        pattern = "canal_alcista"
    elif s_slope < -0.05 and r_slope < -0.05:
        pattern = "canal_bajista"
    else:
        pattern = "rango_lateral"

    # Canales: se dibuja la linea de tendencia del lado de la tendencia
    # (minimos en alcista, maximos en bajista) y la opuesta como PARALELA que
    # contiene todas las mechas. La arista superior independiente del hull en
    # una suba acelerada es una cuerda inicio->ATH que queda muy por encima de
    # las velas recientes; la paralela no tiene ese problema.
    if pattern == "canal_alcista":
        r = _parallel_edge(df, s, start_idx, end_idx, "upper")
    elif pattern == "canal_bajista":
        s = _parallel_edge(df, r, start_idx, end_idx, "lower")

    lines = []
    for edge in (s, r):
        ext = _extend_edge_to_target(edge, future_target_idx)
        (a1, ap1), (a2, ap2) = ext
        lines.append({"width": 2, "data": _line_points(df, a1, ap1, a2, ap2, bar_days)})
    return lines, pattern


# --------------------------------------------------------------------------
# Senal compuesta ("semaforo"): 9 votos -1/0/+1
# --------------------------------------------------------------------------
def composite_signal(last):
    votes = {}
    price = last["close"]

    votes["precio_vs_sma20"] = 1 if price > last["sma20"] else -1
    votes["precio_vs_sma50"] = 1 if price > last["sma50"] else -1
    votes["precio_vs_sma200"] = 1 if not np.isnan(last["sma200"]) and price > last["sma200"] else (
        -1 if not np.isnan(last["sma200"]) else 0)
    votes["sma20_vs_sma50"] = 1 if last["sma20"] > last["sma50"] else -1

    rsi = last["rsi"]
    if rsi >= 70:
        votes["rsi"] = -1
    elif rsi <= 30:
        votes["rsi"] = 1
    elif rsi >= 50:
        votes["rsi"] = 1
    else:
        votes["rsi"] = -1

    votes["macd_hist"] = 1 if last["macd_hist"] > 0 else (-1 if last["macd_hist"] < 0 else 0)
    votes["macd_vs_signal"] = 1 if last["macd"] > last["macd_signal"] else -1

    if not np.isnan(last.get("marron", np.nan)) and not np.isnan(last.get("media", np.nan)):
        votes["koncorde_cruce"] = 1 if last["marron"] > last["media"] else -1
    else:
        votes["koncorde_cruce"] = 0

    if not np.isnan(last.get("azul", np.nan)):
        votes["koncorde_manos_fuertes"] = 1 if last["azul"] > 0 else -1
    else:
        votes["koncorde_manos_fuertes"] = 0

    total = sum(votes.values())
    n_buy = sum(1 for v in votes.values() if v > 0)
    n_sell = sum(1 for v in votes.values() if v < 0)
    n_neutral = sum(1 for v in votes.values() if v == 0)

    if total <= -5:
        label = "Venta fuerte"
    elif total <= -2:
        label = "Venta"
    elif total < 2:
        label = "Neutral"
    elif total < 5:
        label = "Compra"
    else:
        label = "Compra fuerte"

    return {
        "votes": votes,
        "score": total,
        "max_score": len(votes),
        "n_buy": n_buy,
        "n_sell": n_sell,
        "n_neutral": n_neutral,
        "label": label,
    }


# --------------------------------------------------------------------------
# Orquestacion
# --------------------------------------------------------------------------
def analyze(input_path, ticker, company, outdir, currency="USD", interval="weekly"):
    import os
    os.makedirs(outdir, exist_ok=True)

    # bars_per_week: cuantas velas entran en una semana de calendario (1 en
    # semanal, 5 en diario por las ruedas habiles). bars_per_year: cuantas
    # velas entran en un anio (52 semanal, 252 diario). Se usan para reescalar
    # a tiempo real los parametros de deteccion que antes asumian semanal.
    bars_per_week = 5.0 if interval == "daily" else 1.0
    bars_per_year = 252 if interval == "daily" else 52

    df = load_raw(input_path)
    df = add_smas(df)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_koncorde(df)

    last = df.iloc[-1]
    current_price = float(last["close"])
    ath_price, ath_date = find_ath(df)

    levels = find_support_resistance(df, bars_per_week=bars_per_week)
    legs = find_major_legs(df, bars_per_week=bars_per_week)
    last_date = df["datetime"].max()
    bar_days = _median_bar_days(df)
    # extender los canales/linea de ATH ~180 dias de calendario hacia adelante,
    # expresado en velas segun el espaciado real de los datos (no fijo a 1 semana)
    extension_bars = 180.0 / bar_days if bar_days > 0 else 180.0 / 7.0
    future_target_idx = (len(df) - 1) + extension_bars

    channel_lines = historical_channels(df, legs, future_target_idx, bar_days)
    recent_lines, structure_pattern = recent_structure(df, 2, future_target_idx, bar_days, bars_per_week)

    signal = composite_signal(last)

    # 52 semanas high/low (aprox 1 anio; bars_per_year ya equivale a eso en
    # cualquier temporalidad)
    last_52 = df.tail(int(round(bars_per_year)))
    high_52w = float(last_52["high"].max())
    low_52w = float(last_52["low"].min())

    nearest_below = [l for l in levels if l["price"] < current_price]
    nearest_above = [l for l in levels if l["price"] > current_price]
    nearest_support = max(nearest_below, key=lambda x: x["price"]) if nearest_below else None
    nearest_resistance = min(nearest_above, key=lambda x: x["price"]) if nearest_above else None

    analysis = {
        "ticker": ticker,
        "company": company,
        "currency": currency,
        "interval": interval,
        "timeframe_adj": "diarios" if interval == "daily" else "semanales",
        "timeframe_label": "diaria" if interval == "daily" else "semanal",
        "as_of": last["datetime"].strftime("%Y-%m-%d"),
        "current_price": round(current_price, 2),
        "ath_price": round(ath_price, 2),
        "ath_date": ath_date.strftime("%Y-%m-%d"),
        "pct_from_ath": round((current_price / ath_price - 1) * 100, 2),
        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
        "sma20": round(float(last["sma20"]), 2) if not np.isnan(last["sma20"]) else None,
        "sma50": round(float(last["sma50"]), 2) if not np.isnan(last["sma50"]) else None,
        "sma200": round(float(last["sma200"]), 2) if not np.isnan(last["sma200"]) else None,
        "rsi14": round(float(last["rsi"]), 1) if not np.isnan(last["rsi"]) else None,
        "macd": round(float(last["macd"]), 3),
        "macd_signal": round(float(last["macd_signal"]), 3),
        "macd_hist": round(float(last["macd_hist"]), 3),
        "koncorde_marron": round(float(last["marron"]), 1) if not np.isnan(last["marron"]) else None,
        "koncorde_media": round(float(last["media"]), 1) if not np.isnan(last["media"]) else None,
        "koncorde_azul": round(float(last["azul"]), 1) if not np.isnan(last["azul"]) else None,
        "koncorde_verde": round(float(last["verde"]), 1) if not np.isnan(last["verde"]) else None,
        "support_resistance_levels": levels,
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
        "structure_pattern_2y": structure_pattern,
        "n_historical_channels": len(legs),
        "signal": signal,
        "n_bars": len(df),
        "data_start": df["datetime"].min().strftime("%Y-%m-%d"),
        "data_end": df["datetime"].max().strftime("%Y-%m-%d"),
    }

    with open(f"{outdir}/analysis.json", "w") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    # ---- chart_data.js ----
    def series_json(col, round_dec=4):
        d = df[["datetime", col]].dropna()
        items = ['{time:"%s",value:%s}' % (dt.strftime("%Y-%m-%d"), round(float(v), round_dec))
                 for dt, v in zip(d["datetime"], d[col])]
        return "[" + ",".join(items) + "]"

    def candles_json():
        d = df[["datetime", "open", "high", "low", "close"]].dropna()
        items = []
        for dt, o, h, l, c in zip(d["datetime"], d["open"], d["high"], d["low"], d["close"]):
            items.append('{time:"%s",open:%s,high:%s,low:%s,close:%s}' %
                          (dt.strftime("%Y-%m-%d"), round(o, 4), round(h, 4), round(l, 4), round(c, 4)))
        return "[" + ",".join(items) + "]"

    def macd_hist_json():
        d = df[["datetime", "macd_hist"]].dropna()
        items = []
        for dt, v in zip(d["datetime"], d["macd_hist"]):
            color = "'#008300'" if v >= 0 else "'#e34948'"
            items.append('{time:"%s",value:%s,color:%s}' % (dt.strftime("%Y-%m-%d"), round(float(v), 4), color))
        return "[" + ",".join(items) + "]"

    def koncorde_hist_json(col, color):
        d = df[["datetime", col]].dropna()
        items = []
        for dt, v in zip(d["datetime"], d[col]):
            items.append('{time:"%s",value:%s,color:"%s"}' % (dt.strftime("%Y-%m-%d"), round(float(v), 3), color))
        return "[" + ",".join(items) + "]"

    def edge_js(line):
        return "{width:%d,data:%s}" % (line["width"], json.dumps(line["data"], separators=(",", ":")))

    special_levels = []
    lines_js = []
    for l in levels:
        lines_js.append('{price:%s,title:"%s toques",color:"rgba(158,158,158,0.9)",lineStyle:2}' %
                         (l["price"], l["touches"]))

    future_date_str = _idx_to_date_str(df, future_target_idx, bar_days)
    default_range = "1y" if interval == "daily" else "3y"

    js_parts = []
    js_parts.append("const candles = %s;" % candles_json())
    js_parts.append("const sma20 = %s;" % series_json("sma20"))
    js_parts.append("const sma50 = %s;" % series_json("sma50"))
    js_parts.append("const sma200 = %s;" % series_json("sma200"))
    js_parts.append("const rsiData = %s;" % series_json("rsi", 2))
    js_parts.append("const macdData = %s;" % series_json("macd", 4))
    js_parts.append("const macdSignalData = %s;" % series_json("macd_signal", 4))
    js_parts.append("const macdHistData = %s;" % macd_hist_json())
    js_parts.append("const verdeHist = %s;" % koncorde_hist_json("verde", "rgba(87,227,137,0.55)"))
    js_parts.append("const marronHist = %s;" % koncorde_hist_json("marron", "rgba(240,168,96,0.55)"))
    js_parts.append("const azulHist = %s;" % koncorde_hist_json("azul", "rgba(62,203,240,0.55)"))
    js_parts.append("const mediaData = %s;" % series_json("media", 3))
    js_parts.append("const srLevels = [\n  " + ",\n  ".join(lines_js) + "\n];")
    js_parts.append("const channelLines = [\n  " + ",\n  ".join(edge_js(l) for l in channel_lines) + "\n];")
    js_parts.append("const recentStructureLines = [\n  " + ",\n  ".join(edge_js(l) for l in recent_lines) + "\n];")
    js_parts.append("const athLine = {price:%.2f,startTime:'%s',endTime:'%s'};" %
                     (ath_price, ath_date.strftime("%Y-%m-%d"), future_date_str))
    js_parts.append("const gaugeScore = %d;" % signal["score"])
    js_parts.append("const gaugeMaxScore = %d;" % signal["max_score"])
    js_parts.append("const gaugeLabel = %s;" % json.dumps(signal["label"], ensure_ascii=False))
    js_parts.append("const defaultRange = %s;" % json.dumps(default_range))

    with open(f"{outdir}/chart_data.js", "w") as f:
        f.write("\n".join(js_parts) + "\n")

    return analysis


def build_report(analysis):
    a = analysis
    cur = a["currency"]
    lines = []
    lines.append(f"# Analisis tecnico: {a['company']} ({a['ticker']})")
    lines.append("")
    lines.append(f"Datos {a['timeframe_adj']} desde {a['data_start']} hasta {a['data_end']} ({a['n_bars']} velas).")
    lines.append("")

    lines.append("## Precio y estructura")
    lines.append(f"- Precio actual: {cur} {a['current_price']}")
    lines.append(f"- Maximo historico (cierre/apertura, sin mechas): {cur} {a['ath_price']} el {a['ath_date']} "
                 f"({a['pct_from_ath']:+.2f}% desde ahi)")
    lines.append(f"- Rango de las ultimas 52 semanas: {cur} {a['low_52w']} - {cur} {a['high_52w']}")
    pattern_map = {
        "canal_alcista": "canal/bandera alcista (soporte y resistencia paralelos, subiendo)",
        "canal_bajista": "canal/bandera bajista (soporte y resistencia paralelos, bajando)",
        "triangulo_simetrico": "triangulo simetrico (soporte subiendo, resistencia bajando: compresion)",
        "triangulo_ascendente": "triangulo ascendente (resistencia plana, soporte subiendo)",
        "triangulo_descendente": "triangulo descendente (soporte plano, resistencia bajando)",
        "rango_lateral": "rango lateral (sin pendiente clara)",
        "indeterminado": "sin datos suficientes",
    }
    lines.append(f"- Estructura de los ultimos 2 anios: {pattern_map.get(a['structure_pattern_2y'], a['structure_pattern_2y'])}")
    if a["nearest_support"]:
        lines.append(f"- Soporte mas cercano por debajo: {cur} {a['nearest_support']['price']} "
                     f"({a['nearest_support']['touches']} toques historicos)")
    if a["nearest_resistance"]:
        lines.append(f"- Resistencia mas cercana por encima: {cur} {a['nearest_resistance']['price']} "
                     f"({a['nearest_resistance']['touches']} toques historicos)")
    lines.append("")

    lines.append("## Medias moviles")
    sma20, sma50, sma200 = a["sma20"], a["sma50"], a["sma200"]
    price = a["current_price"]
    if sma20 and sma50 and sma200:
        if price > sma20 > sma50 > sma200:
            trend = "alineacion alcista completa (precio > SMA20 > SMA50 > SMA200): tendencia de fondo solida"
        elif price < sma20 < sma50 < sma200:
            trend = "alineacion bajista completa (precio < SMA20 < SMA50 < SMA200): tendencia de fondo debil"
        else:
            trend = "medias mezcladas, sin alineacion clara: posible transicion o lateralizacion"
        lines.append(f"- SMA20: {cur} {sma20} | SMA50: {cur} {sma50} | SMA200: {cur} {sma200}")
        lines.append(f"- Lectura: {trend}")
    lines.append("")

    lines.append("## RSI (14)")
    rsi = a["rsi14"]
    if rsi is not None:
        if rsi >= 70:
            rsi_read = "sobrecompra: el precio subio fuerte y rapido, riesgo de correccion de corto plazo"
        elif rsi <= 30:
            rsi_read = "sobreventa: el precio cayo fuerte y rapido, posible zona de rebote"
        elif rsi >= 50:
            rsi_read = "momentum alcista sano, sin sobrecompra"
        else:
            rsi_read = "momentum debil/bajista, sin sobreventa"
        lines.append(f"- RSI: {rsi} -> {rsi_read}")
    lines.append("")

    lines.append("## MACD (12, 26, 9)")
    macd, macd_sig, macd_hist = a["macd"], a["macd_signal"], a["macd_hist"]
    cross = "MACD por encima de la senal (sesgo alcista)" if macd > macd_sig else "MACD por debajo de la senal (sesgo bajista)"
    hist_dir = "histograma positivo y momentum a favor" if macd_hist > 0 else "histograma negativo, momentum en contra"
    lines.append(f"- MACD: {macd} | Senal: {macd_sig} | Histograma: {macd_hist}")
    lines.append(f"- Lectura: {cross}; {hist_dir}")
    lines.append("")

    lines.append("## Koncorde (reconstruccion aproximada, no oficial)")
    marron, media, azul, verde = a["koncorde_marron"], a["koncorde_media"], a["koncorde_azul"], a["koncorde_verde"]
    if marron is not None:
        cruce = "tendencia (marron) por encima de su media de senal: sesgo de entrada" if marron > media else \
                "tendencia (marron) por debajo de su media de senal: sesgo de salida"
        fuerza = "manos fuertes en terreno comprador (azul positivo)" if azul and azul > 0 else \
                 "manos fuertes vendiendo o ausentes (azul negativo)"
        lines.append(f"- Tendencia: {marron} | Media de senal: {media} | Manos fuertes: {azul} | Manos debiles: {verde}")
        lines.append(f"- Lectura: {cruce}; {fuerza}")
    lines.append("")

    s = a["signal"]
    lines.append("## Senal compuesta (semaforo)")
    lines.append(f"**{s['label']}** — {s['n_buy']} senales de compra, {s['n_sell']} de venta, "
                 f"{s['n_neutral']} neutrales, sobre {s['max_score']} indicadores evaluados "
                 f"(puntaje neto: {s['score']:+d}).")
    lines.append("")
    lines.append("_Metodologia propia: cada indicador vota compra (+1), venta (-1) o neutral (0); "
                 "el puntaje neto se traduce en 5 niveles. No es una recomendacion de inversion._")

    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--company", required=True)
    ap.add_argument("--currency", default="USD")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--interval", required=True, choices=["daily", "weekly"],
                     help="Temporalidad de las velas: 'daily' o 'weekly'. Tiene que "
                          "coincidir con el interval pedido a Twelve Data en el paso 1.")
    args = ap.parse_args()

    analysis = analyze(args.input, args.ticker, args.company, args.outdir, args.currency, args.interval)
    report = build_report(analysis)
    with open(f"{args.outdir}/report.md", "w") as f:
        f.write(report)

    print(json.dumps({"ok": True, "signal": analysis["signal"]["label"], "score": analysis["signal"]["score"]}))
```

## scripts/gauge.py

```python
"""Genera el SVG del semaforo (gauge tipo velocimetro) y su tarjeta HTML."""
import math

ARC_COLORS = ["#c0392b", "#f1948a", "#d5d8dc", "#a9dfbf", "#1e8449"]
ZONE_LABELS = ["Venta fuerte", "Venta", "Neutral", "Compra", "Compra fuerte"]

PILL_STYLES = {
    "Venta fuerte": ("#c0392b", "#ffffff"),
    "Venta": ("#f1948a", "#7b241c"),
    "Neutral": ("#d5d8dc", "#4a4a4a"),
    "Compra": ("#a9dfbf", "#186a3b"),
    "Compra fuerte": ("#1e8449", "#ffffff"),
}


def _point(cx, cy, r, theta_deg):
    t = math.radians(theta_deg)
    return cx + r * math.cos(t), cy - r * math.sin(t)


def gauge_svg(score, max_score, label, width=220, height=140):
    cx, cy = width / 2, height - 20
    r = 82
    stroke_w = 20

    bounds = [180 - i * (180 / 5) for i in range(6)]  # [180,144,108,72,36,0]
    segments = []
    for i in range(5):
        a1, a2 = bounds[i], bounds[i + 1]
        x1, y1 = _point(cx, cy, r, a1)
        x2, y2 = _point(cx, cy, r, a2)
        segments.append(
            f'<path d="M{x1:.2f},{y1:.2f} A{r},{r} 0 0 1 {x2:.2f},{y2:.2f}" '
            f'fill="none" stroke="{ARC_COLORS[i]}" stroke-width="{stroke_w}" stroke-linecap="butt" />'
        )

    ratio = (score + max_score) / (2 * max_score) if max_score else 0.5
    ratio = min(max(ratio, 0), 1)
    theta_needle = 180 - ratio * 180
    nx, ny = _point(cx, cy, r - 28, theta_needle)

    needle = (
        f'<line x1="{cx}" y1="{cy}" x2="{nx:.2f}" y2="{ny:.2f}" '
        f'stroke="#3a3a38" stroke-width="3.5" stroke-linecap="round" />'
        f'<circle cx="{cx}" cy="{cy}" r="6" fill="#3a3a38" />'
    )

    svg = (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="Semaforo tecnico: {label}, puntaje {score} de {max_score}">'
        + "".join(segments)
        + needle
        + "</svg>"
    )
    return svg


def gauge_card_html(signal, ticker, currency, current_price):
    score = signal["score"]
    max_score = signal["max_score"]
    label = signal["label"]
    svg = gauge_svg(score, max_score, label)
    pill_bg, pill_text = PILL_STYLES[label]

    votes_line = (
        f"{signal['n_buy']} senales de compra · {signal['n_sell']} de venta · "
        f"{signal['n_neutral']} neutrales (sobre {max_score} indicadores, puntaje neto {score:+d})"
    )

    legend_items = "".join(
        f'<span><span class="swatch" style="background:{ARC_COLORS[i]};"></span>{ZONE_LABELS[i]}</span>'
        for i in range(5)
    )

    html = f'''<div class="gauge-card">
    <div class="gauge-svg-wrap">
      {svg}
      <div class="legend gauge-legend">{legend_items}</div>
    </div>
    <div class="gauge-info">
      <p class="gauge-title">Resumen tecnico — {ticker} a {currency} {current_price}</p>
      <span class="gauge-pill" style="background:{pill_bg}; color:{pill_text};">{label}</span>
      <p class="gauge-votes">{votes_line}</p>
      <p class="gauge-disclaimer">Senal propia combinando SMA, RSI, MACD y Koncorde. No es una recomendacion de inversion.</p>
    </div>
  </div>'''
    return html
```

## scripts/build_artifact.py

```python
#!/usr/bin/env python3
"""Arma el artifact HTML final combinando template.html + chart_data.js + gauge.

Uso:
  python3 build_artifact.py --outdir OUT/KO --script-dir SCRIPTS/
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gauge import gauge_card_html  # noqa: E402


def build(outdir, script_dir):
    with open(f"{outdir}/analysis.json") as f:
        a = json.load(f)
    with open(f"{outdir}/chart_data.js") as f:
        chart_js = f.read()
    with open(f"{script_dir}/template.html") as f:
        template = f.read()

    ticker = a["ticker"]
    company = a["company"]
    currency = a["currency"]
    current_price = a["current_price"]

    gauge_html = gauge_card_html(a["signal"], ticker, currency, current_price)

    interval = a.get("interval", "weekly")
    tf_word = "diarias" if interval == "daily" else "semanales"  # "velas ___"
    tf_unit = "sesiones" if interval == "daily" else "semanas"  # "20/50/200 ___"

    title = f"{ticker} - Analisis tecnico con SMA, RSI, MACD, Koncorde y semaforo"
    h1 = f"{ticker} - {company}"
    subtitle = (
        f"Velas {tf_word}, historico completo ({a['data_start'][:4]} - hoy), "
        f"con SMA 20/50/200, RSI 14, MACD, Koncorde (aprox.), soportes/resistencias, "
        f"canales de tendencia y semaforo tecnico."
    )

    out = template
    out = out.replace("__TITLE__", title)
    out = out.replace("__H1__", h1)
    out = out.replace("__SUBTITLE__", subtitle)
    out = out.replace("__GAUGE_CARD__", gauge_html)
    out = out.replace("__CHART_DATA_JS__", chart_js)
    out = out.replace("__ARIA_MAIN__",
                       f"Grafico de velas {tf_word} de {ticker} con medias moviles de 20, 50 y 200 {tf_unit}, "
                       f"soportes, resistencias, canales de tendencia y maximo historico")
    out = out.replace("__ARIA_RSI__", f"Indicador RSI de 14 {tf_unit} para {ticker}")
    out = out.replace("__ARIA_MACD__", f"Indicador MACD para {ticker}")
    out = out.replace("__ARIA_KON__",
                       f"Reconstruccion aproximada del indicador Koncorde para {ticker}, "
                       f"con las tres capas superpuestas con transparencia")

    out_path = f"{outdir}/artifact.html"
    with open(out_path, "w") as f:
        f.write(out)
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--script-dir", required=True)
    args = ap.parse_args()
    path = build(args.outdir, args.script_dir)
    print(json.dumps({"ok": True, "path": path}))
```

## scripts/template.html

```html
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>__TITLE__</title>
<style>
  :root {
    --bg: #fcfcfb;
    --text-primary: #0b0b0b;
    --text-secondary: #52514e;
    --border: rgba(11,11,11,0.10);
    --grid: #e1e0d9;
    --surface1: #f1efe8;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #1a1a19;
      --text-primary: #f0efec;
      --text-secondary: #c3c2b7;
      --border: rgba(255,255,255,0.10);
      --grid: #2c2c2a;
      --surface1: #232322;
    }
  }
  :root[data-theme="dark"] {
    --bg: #1a1a19;
    --text-primary: #f0efec;
    --text-secondary: #c3c2b7;
    --border: rgba(255,255,255,0.10);
    --grid: #2c2c2a;
    --surface1: #232322;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    padding: 1.5rem;
  }
  h1 { font-size: 18px; font-weight: 500; margin: 0 0 4px; }
  p.subtitle { font-size: 13px; color: var(--text-secondary); margin: 0 0 1rem; }
  .toolbar { display: flex; gap: 8px; margin-bottom: 1rem; flex-wrap: wrap; }
  .toolbar button {
    font-size: 12px; padding: 6px 12px; border-radius: 6px;
    border: 0.5px solid var(--border); background: var(--surface1);
    color: var(--text-primary); cursor: pointer;
  }
  .toolbar button.active { border-color: #378add; color: #185fa5; }
  .panel { margin-bottom: 8px; }
  .panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 6px; }
  .legend { display: flex; gap: 14px; font-size: 12px; color: var(--text-secondary); flex-wrap: wrap; }
  .legend span { display: flex; align-items: center; gap: 4px; }
  .swatch { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
  .pane-label { font-size: 12px; color: var(--text-secondary); font-weight: 500; }
  .note { font-size: 11px; color: var(--text-secondary); margin: 4px 0 0; }
  #chart_main, #chart_rsi, #chart_macd, #chart_konkorde {
    width: 100%; border: 0.5px solid var(--border); border-radius: 12px; overflow: hidden;
  }
  #chart_main { height: 400px; }
  #chart_rsi { height: 140px; margin-top: 8px; }
  #chart_macd { height: 150px; margin-top: 8px; }
  #chart_konkorde { height: 190px; margin-top: 8px; }

  .gauge-card {
    display: flex; align-items: center; gap: 20px; flex-wrap: wrap;
    border: 0.5px solid var(--border); border-radius: 12px; padding: 1rem 1.25rem;
    margin-bottom: 1.25rem; background: var(--surface1);
  }
  .gauge-svg-wrap { flex: 0 0 auto; }
  .gauge-info { flex: 1 1 220px; min-width: 200px; }
  .gauge-title { font-size: 13px; color: var(--text-secondary); margin: 0 0 6px; }
  .gauge-pill {
    display: inline-block; padding: 6px 16px; border-radius: 999px;
    font-size: 14px; font-weight: 500; margin-bottom: 8px;
  }
  .gauge-votes { font-size: 12px; color: var(--text-secondary); margin: 0; line-height: 1.5; }
  .gauge-disclaimer { font-size: 11px; color: var(--text-secondary); margin: 6px 0 0; }
  .gauge-legend { max-width: 220px; justify-content: center; gap: 8px 10px; margin-top: -6px; }
  .gauge-legend span { font-size: 10.5px; }
</style>
</head>
<body>
  <h1>__H1__</h1>
  <p class="subtitle">__SUBTITLE__</p>

  __GAUGE_CARD__

  <div class="toolbar">
    <button data-range="6m">6M</button>
    <button data-range="1y">1A</button>
    <button data-range="3y">3A</button>
    <button data-range="5y">5A</button>
    <button data-range="10y">10A</button>
    <button data-range="all">Todo</button>
  </div>

  <div class="panel">
    <div class="panel-header">
      <span class="legend">
        <span><span class="swatch" style="background:#eda100;"></span>SMA 20</span>
        <span><span class="swatch" style="background:#e34948;"></span>SMA 50</span>
        <span><span class="swatch" style="background:#6250d6;"></span>SMA 200</span>
        <span><span class="swatch" style="background:#1a56db;"></span>Maximo historico</span>
      </span>
    </div>
    <div id="chart_main" role="img" aria-label="__ARIA_MAIN__"></div>
  </div>

  <div class="panel">
    <div class="panel-header"><span class="pane-label">RSI (14)</span></div>
    <div id="chart_rsi" role="img" aria-label="__ARIA_RSI__"></div>
  </div>

  <div class="panel">
    <div class="panel-header">
      <span class="pane-label">MACD (12, 26, 9)</span>
      <span class="legend">
        <span><span class="swatch" style="background:#378add;"></span>MACD</span>
        <span><span class="swatch" style="background:#eb6834;"></span>Signal</span>
      </span>
    </div>
    <div id="chart_macd" role="img" aria-label="__ARIA_MACD__"></div>
  </div>

  <div class="panel">
    <div class="panel-header">
      <span class="pane-label">Koncorde (aprox. no oficial)</span>
      <span class="legend">
        <span><span class="swatch" style="background:#3ecbf0;"></span>Manos fuertes</span>
        <span><span class="swatch" style="background:#f0a860;"></span>Tendencia</span>
        <span><span class="swatch" style="background:#57e389;"></span>Manos debiles</span>
        <span><span class="swatch" style="background:#e03131;"></span>Media</span>
      </span>
    </div>
    <div id="chart_konkorde" role="img" aria-label="__ARIA_KON__"></div>
    <p class="note">Reconstruccion propia no oficial basada en la formula publica de Blai5 (2008): PVI/NVI + RSI + MFI + oscilador de Bollinger + Estocastico. Las tres capas se muestran siempre superpuestas con transparencia.</p>
  </div>

<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<script>
(function(){

__CHART_DATA_JS__

  const mainEl = document.getElementById('chart_main');
  const rsiEl = document.getElementById('chart_rsi');
  const macdEl = document.getElementById('chart_macd');
  const konEl = document.getElementById('chart_konkorde');

  if (typeof LightweightCharts === 'undefined') {
    [mainEl, rsiEl, macdEl, konEl].forEach(el => {
      el.innerHTML = '<div style="padding:2rem; text-align:center; color: var(--text-secondary); font-size:14px;">No se pudo cargar la libreria de graficos. Proba recargar la pagina.</div>';
    });
    return;
  }

  function isDarkMode() {
    const attr = document.documentElement.getAttribute('data-theme');
    if (attr === 'dark') return true;
    if (attr === 'light') return false;
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  }

  const dark = isDarkMode();
  const textColor = dark ? '#c3c2b7' : '#52514e';
  const gridColor = dark ? '#2c2c2a' : '#e1e0d9';

  function baseOptions(el) {
    return {
      layout: { background: { color: 'transparent' }, textColor: textColor },
      grid: { vertLines: { color: 'transparent' }, horzLines: { color: gridColor } },
      rightPriceScale: { borderColor: gridColor },
      timeScale: { borderColor: gridColor, timeVisible: false, rightOffset: 12 },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
      width: el.clientWidth,
      height: el.clientHeight
    };
  }

  const chartMain = LightweightCharts.createChart(mainEl, baseOptions(mainEl));
  const candleSeries = chartMain.addCandlestickSeries({
    upColor: '#008300', downColor: '#e34948', borderVisible: false,
    wickUpColor: '#008300', wickDownColor: '#e34948'
  });
  candleSeries.setData(candles);
  chartMain.addLineSeries({ color: '#eda100', lineWidth: 2, priceLineVisible: false, lastValueVisible: false }).setData(sma20);
  chartMain.addLineSeries({ color: '#e34948', lineWidth: 2, priceLineVisible: false, lastValueVisible: false }).setData(sma50);
  chartMain.addLineSeries({ color: '#6250d6', lineWidth: 2, priceLineVisible: false, lastValueVisible: false }).setData(sma200);

  srLevels.forEach(lvl => {
    candleSeries.createPriceLine({
      price: lvl.price,
      color: lvl.color,
      lineWidth: 1,
      lineStyle: lvl.lineStyle,
      axisLabelVisible: true,
      title: lvl.title
    });
  });

  chartMain.addLineSeries({ color: '#1a56db', lineWidth: 4, lineStyle: 0, priceLineVisible: false, lastValueVisible: false })
    .setData([{ time: athLine.startTime, value: athLine.price }, { time: athLine.endTime, value: athLine.price }]);

  const structureColor = dark ? '#e8e8e8' : '#1a1a1a';
  channelLines.forEach(l => {
    chartMain.addLineSeries({ color: structureColor, lineWidth: l.width, lineStyle: 0, priceLineVisible: false, lastValueVisible: false }).setData(l.data);
  });
  recentStructureLines.forEach(l => {
    chartMain.addLineSeries({ color: structureColor, lineWidth: l.width, lineStyle: 0, priceLineVisible: false, lastValueVisible: false }).setData(l.data);
  });

  const chartRsi = LightweightCharts.createChart(rsiEl, baseOptions(rsiEl));
  const rsiSeries = chartRsi.addLineSeries({ color: '#378add', lineWidth: 2, lastValueVisible: false });
  rsiSeries.setData(rsiData);
  rsiSeries.createPriceLine({ price: 70, color: '#e34948', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: '70' });
  rsiSeries.createPriceLine({ price: 30, color: '#008300', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: '30' });

  const chartMacd = LightweightCharts.createChart(macdEl, baseOptions(macdEl));
  const macdHistSeries = chartMacd.addHistogramSeries({ priceFormat: { type: 'price' } });
  macdHistSeries.setData(macdHistData);
  chartMacd.addLineSeries({ color: '#378add', lineWidth: 2, priceLineVisible: false, lastValueVisible: false }).setData(macdData);
  chartMacd.addLineSeries({ color: '#eb6834', lineWidth: 2, priceLineVisible: false, lastValueVisible: false }).setData(macdSignalData);

  const chartKon = LightweightCharts.createChart(konEl, baseOptions(konEl));
  const verdeSeries = chartKon.addHistogramSeries({ priceFormat: { type: 'price' } });
  verdeSeries.setData(verdeHist);
  const marronSeries = chartKon.addHistogramSeries({ priceFormat: { type: 'price' } });
  marronSeries.setData(marronHist);
  const azulSeries = chartKon.addHistogramSeries({ priceFormat: { type: 'price' } });
  azulSeries.setData(azulHist);
  chartKon.addLineSeries({ color: '#e03131', lineWidth: 2, priceLineVisible: false, lastValueVisible: false }).setData(mediaData);

  const charts = [chartMain, chartRsi, chartMacd, chartKon];
  const elems = [mainEl, rsiEl, macdEl, konEl];
  let syncing = false;
  charts.forEach(chart => {
    chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
      if (syncing || !range) return;
      syncing = true;
      charts.forEach(c => { if (c !== chart) c.timeScale().setVisibleLogicalRange(range); });
      syncing = false;
    });
  });

  function applyRange(label) {
    const lastTime = candles[candles.length - 1].time;
    const lastDate = new Date(lastTime + 'T00:00:00Z');
    const toDate = new Date(lastDate);
    toDate.setUTCDate(toDate.getUTCDate() + 180);
    const toStr = toDate.toISOString().slice(0,10);
    if (label === 'all') {
      chartMain.timeScale().fitContent();
      return;
    }
    const fromDate = new Date(lastDate);
    if (label === '6m') {
      fromDate.setUTCMonth(fromDate.getUTCMonth() - 6);
    } else {
      const years = { '1y': 1, '3y': 3, '5y': 5, '10y': 10 }[label];
      fromDate.setUTCFullYear(fromDate.getUTCFullYear() - years);
    }
    const from = fromDate.toISOString().slice(0,10);
    chartMain.timeScale().setVisibleRange({ from: from, to: toStr });
  }

  document.querySelectorAll('.toolbar button').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.toolbar button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      applyRange(btn.dataset.range);
    });
  });

  // defaultRange viene de chart_data.js: '1y' en diario, '3y' en semanal
  const initialRange = (typeof defaultRange !== 'undefined') ? defaultRange : '3y';
  const initialBtn = document.querySelector('.toolbar button[data-range="' + initialRange + '"]');
  if (initialBtn) initialBtn.classList.add('active');
  applyRange(initialRange);

  window.addEventListener('resize', function() {
    charts.forEach((chart, i) => {
      const el = elems[i];
      chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
    });
  });
})();
</script>
</body>
</html>
```

## Dependencias de Python

`pandas`, `numpy`, `scipy` (para `scipy.signal.find_peaks`). Si no estan
instaladas: `pip install --break-system-packages pandas numpy scipy`.
