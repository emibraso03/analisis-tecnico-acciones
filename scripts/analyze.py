#!/usr/bin/env python3
"""
Analisis tecnico automatizado de una accion a partir de su historico semanal
(OHLCV) descargado de Twelve Data.

Calcula: SMA20/50/200, RSI14, MACD(12,26,9), volumen (SMA20 de volumen,
RVOL y OBV), una reconstruccion aproximada
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
# Volumen: SMA20 de volumen, volumen relativo (RVOL) y OBV
# --------------------------------------------------------------------------
def has_volume(df):
    v = df["volume"]
    return bool(v.notna().any() and (v.fillna(0) > 0).any())


def add_volume(df, period=20):
    vol = df["volume"].fillna(0)
    df["vol_sma20"] = vol.rolling(period).mean()
    df["rvol"] = vol / df["vol_sma20"].replace(0, np.nan)
    direction = np.sign(df["close"].diff()).fillna(0)
    df["obv"] = (direction * vol).cumsum()
    return df


def volume_confirmation(df, lookback=20):
    """Compara la direccion del precio vs la del OBV en las ultimas `lookback`
    velas (pendiente de una regresion lineal, normalizada por el nivel medio
    para que sea comparable). Devuelve 'confirmacion_alcista',
    'confirmacion_bajista', 'divergencia_bajista' (precio sube, OBV baja),
    'divergencia_alcista' (precio baja, OBV sube) o 'indeterminado'."""
    tail = df.tail(lookback)
    if len(tail) < lookback or tail["obv"].isna().any():
        return "indeterminado"
    x = np.arange(len(tail))
    p_slope = np.polyfit(x, tail["close"].values, 1)[0]
    o_slope = np.polyfit(x, tail["obv"].values, 1)[0]
    if p_slope == 0 or o_slope == 0:
        return "indeterminado"
    if p_slope > 0 and o_slope > 0:
        return "confirmacion_alcista"
    if p_slope < 0 and o_slope < 0:
        return "confirmacion_bajista"
    if p_slope > 0 and o_slope < 0:
        return "divergencia_bajista"
    return "divergencia_alcista"


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
    volume_ok = has_volume(df)
    if volume_ok:
        df = add_volume(df)
    else:
        for c in ["vol_sma20", "rvol", "obv"]:
            df[c] = np.nan
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
        "has_volume": volume_ok,
        "volume_last": int(last["volume"]) if volume_ok and not np.isnan(last["volume"]) else None,
        "volume_sma20": int(last["vol_sma20"]) if volume_ok and not np.isnan(last["vol_sma20"]) else None,
        "rvol": round(float(last["rvol"]), 2) if volume_ok and not np.isnan(last["rvol"]) else None,
        "volume_confirmation": volume_confirmation(df) if volume_ok else "sin_volumen",
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

    def volume_hist_json():
        if not volume_ok:
            return "[]"
        d = df[["datetime", "open", "close", "volume"]].dropna()
        items = []
        for dt, o, c, v in zip(d["datetime"], d["open"], d["close"], d["volume"]):
            color = "rgba(0,131,0,0.45)" if c >= o else "rgba(227,73,72,0.45)"
            items.append('{time:"%s",value:%d,color:"%s"}' % (dt.strftime("%Y-%m-%d"), int(v), color))
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
    js_parts.append("const hasVolume = %s;" % ("true" if volume_ok else "false"))
    js_parts.append("const volumeHist = %s;" % volume_hist_json())
    js_parts.append("const volSmaData = %s;" % (series_json("vol_sma20", 0) if volume_ok else "[]"))
    js_parts.append("const obvData = %s;" % (series_json("obv", 0) if volume_ok else "[]"))
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

    lines.append("## Volumen")
    if a.get("has_volume"):
        rvol = a["rvol"]
        if rvol is None:
            rvol_read = "sin historia suficiente para la SMA20 de volumen"
        elif rvol >= 2:
            rvol_read = "volumen muy por encima de lo normal: movimiento con participacion fuerte"
        elif rvol >= 1.2:
            rvol_read = "volumen por encima de lo normal"
        elif rvol <= 0.6:
            rvol_read = "volumen muy por debajo de lo normal: movimiento con poca conviccion"
        else:
            rvol_read = "volumen en linea con su media"
        conf_map = {
            "confirmacion_alcista": "precio y OBV suben juntos: la suba esta acompanada por volumen",
            "confirmacion_bajista": "precio y OBV bajan juntos: la baja esta acompanada por volumen",
            "divergencia_bajista": "precio sube pero el OBV baja: suba sin respaldo de volumen (divergencia bajista)",
            "divergencia_alcista": "precio baja pero el OBV sube: acumulacion pese a la caida (divergencia alcista)",
            "indeterminado": "sin direccion clara",
        }
        lines.append(f"- Volumen ultima vela: {a['volume_last']:,} | SMA20 de volumen: "
                     f"{a['volume_sma20']:,} | RVOL: {rvol}" if a["volume_sma20"] is not None else
                     f"- Volumen ultima vela: {a['volume_last']:,}")
        lines.append(f"- Lectura: {rvol_read}")
        lines.append(f"- OBV vs precio (ultimas 20 velas): {conf_map.get(a['volume_confirmation'], a['volume_confirmation'])}")
    else:
        lines.append("- La fuente no trae volumen para este instrumento: panel de volumen omitido.")
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
