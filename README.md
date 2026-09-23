# analisis-tecnico-acciones

Skill para Claude que genera un **análisis técnico gráfico completo** de una acción y lo publica como un **Artifact interactivo**, con un semáforo de señal compuesta (Venta fuerte / Venta / Neutral / Compra / Compra fuerte).

> **Aviso:** proyecto educativo y experimental. Nada de lo que produce es asesoramiento financiero ni una recomendación de inversión. El semáforo es una señal propia y simple, y el Koncorde es una reconstrucción aproximada, no el indicador oficial.

## Qué hace

A partir de un ticker (o el nombre de la empresa) y una temporalidad (**diaria** o **semanal**), calcula y grafica:

- Velas japonesas con SMA 20 / 50 / 200
- RSI (14)
- MACD (12, 26, 9)
- Koncorde aproximado (reconstrucción propia a partir de la fórmula pública de 2008: PVI/NVI + RSI + MFI + Bollinger + Estocástico)
- Soportes y resistencias por giros significativos (con mínimo de toques y vigencia reciente)
- Máximo histórico (usando solo apertura/cierre, sin mechas)
- Canales de tendencia históricos (envolvente convexa, no regresión lineal)
- Estructura de los últimos 2 años (canal, triángulo o rango) con todas las velas, mechas incluidas, dentro de las líneas
- Semáforo: 9 votos (-1 / 0 / +1) que se combinan en un puntaje de -9 a +9 y se muestran en un velocímetro

Los gráficos están sincronizados y usan [TradingView Lightweight Charts](https://github.com/tradingview/lightweight-charts). Además del Artifact, la skill devuelve un informe interpretativo en el chat.

## Estructura

```
analisis-tecnico-acciones/
├── SKILL.md              # la skill (fuente de verdad): flujo, decisiones de diseño y scripts embebidos
├── scripts/
│   ├── analyze.py        # indicadores, niveles, canales y señal compuesta
│   ├── gauge.py          # SVG del semáforo
│   ├── build_artifact.py # arma el HTML final
│   └── template.html     # plantilla del Artifact
├── LICENSE
└── README.md
```

`SKILL.md` embebe el código de `scripts/` porque así la skill lo reconstruye dentro de Claude. La carpeta `scripts/` es una copia para que se pueda leer y probar cómodamente en GitHub.

## Cómo usarla

1. Copiá la carpeta en tu entorno de skills de Claude (o cargá `SKILL.md` como skill personalizada).
2. Conectá una fuente de datos. La skill usa el conector **Twelve Data** para traer las velas (no incluye ninguna credencial; la autenticación la maneja el conector).
3. Pedile a Claude algo como: *"hacé el análisis técnico de KO en semanal"*. Si no aclarás la temporalidad, la skill te pregunta.

## Correr los scripts por fuera de Claude

Si ya tenés un CSV de Twelve Data (`datetime;open;high;low;close;volume`):

```bash
pip install pandas numpy scipy

python3 scripts/analyze.py --input KO_weekly_raw.csv --ticker KO \
  --company "The Coca-Cola Company" --outdir out/KO --currency USD --interval weekly

python3 scripts/build_artifact.py --outdir out/KO --script-dir scripts
```

Abrí `out/KO/artifact.html` en el navegador. El informe en texto queda en `out/KO/report.md`.

## Limitaciones conocidas

- El Koncorde no es el oficial de TradingView/Blai5; no hay forma de replicarlo exacto sin su código fuente.
- El semáforo pondera igual los 9 indicadores y no considera fundamentales, noticias ni contexto de mercado.
- El detalle diario cubre hasta unas 5000 velas (unos 20 años).
- Probado con KO, MELI y GOOG, y con series sintéticas en ambas temporalidades. Faltan más tickers y casos borde.

## Feedback

Me interesa sobre todo saber:

- Si las reglas del semáforo y sus umbrales te parecen razonables.
- Si los soportes/resistencias y canales detectados coinciden con lo que marcarías a mano.
- Qué indicadores agregarías o sacarías.

Abrí un *issue* o escribime.

## Licencia

MIT. Ver [LICENSE](LICENSE).
