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
