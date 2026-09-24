# Notas y decisiones de diseno (por que esta hecho asi)

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
- **Volumen**: panel propio debajo del grafico de velas, sincronizado con el
  resto. Histograma de volumen coloreado por direccion de la vela (verde si
  close >= open, rojo si no, con transparencia), SMA20 de volumen (linea) y
  OBV (On-Balance Volume) en el eje IZQUIERDO del mismo panel, porque su
  escala no es comparable con la del volumen. En el informe se reporta el
  volumen relativo (RVOL = volumen de la ultima vela / SMA20 de volumen) y la
  confirmacion precio-volumen: se compara la pendiente del OBV contra la del
  precio en las ultimas 20 velas (misma direccion = confirmacion; direcciones
  opuestas = divergencia). El volumen NO vota en el semaforo (sigue en 9
  votos): la escala -9..+9 y sus umbrales estan calibrados asi, y el
  Koncorde ya incorpora volumen via PVI/NVI y MFI. Si la serie no trae
  volumen (todo NaN o cero, p.ej. indices o forex en Twelve Data), el panel
  se oculta y el informe lo aclara, sin romper el pipeline. Ojo: en diario,
  Twelve Data informa el volumen de la plaza principal del ticker, no el
  consolidado de todas las plazas.
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
