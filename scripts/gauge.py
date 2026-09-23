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
