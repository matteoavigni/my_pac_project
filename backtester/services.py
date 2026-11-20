from concurrent.futures import ThreadPoolExecutor
import math
import numpy as np
import pandas as pd
import yfinance as yf
from django.core.cache import cache

from .etf_catalog import get_catalog_entry

META_CACHE_TTL = 60 * 60 * 24  # 24 ore
HIST_CACHE_TTL = 60 * 60 * 6   # 6 ore
BOLLO_RATE = 0.0020            # Imposta di bollo italiana 0,20% annuo


def _normalize_df_index(df: pd.DataFrame) -> pd.DataFrame:
    """Rimuove la timezone, normalizza a data pura e rimuove eventuali duplicati."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    idx = pd.to_datetime(out.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    out.index = idx.normalize()
    out = out[~out.index.duplicated(keep='last')].sort_index()
    return out


def _extract_currency(ticker_obj) -> str:
    try:
        cur = ticker_obj.fast_info.get('currency')
        if cur:
            return str(cur)
    except Exception:
        pass
    try:
        cur = (ticker_obj.info or {}).get('currency')
        if cur:
            return str(cur)
    except Exception:
        pass
    return 'EUR'


def get_ticker_metadata(ticker: str) -> dict:
    """
    Recupera e mette in cache nome, valuta e prima data disponibile per un ticker.
    """
    clean_ticker = (ticker or '').upper().strip()
    if not clean_ticker:
        return {'valid': False, 'error': 'Inserisci un ticker'}

    cache_key = f'meta:{clean_ticker}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    catalog_item = get_catalog_entry(clean_ticker)

    try:
        ticker_obj = yf.Ticker(clean_ticker)
        # Scarichiamo prima i dati mensili per trovare rapidamente la data minima storica
        hist = ticker_obj.history(period='max', interval='1mo', auto_adjust=False)
        if hist.empty:
            hist = ticker_obj.history(period='max', auto_adjust=False)

        if hist.empty:
            return {'valid': False, 'error': 'Dati non disponibili per questo ticker'}

        hist = _normalize_df_index(hist)
        first_date = hist.index[0].date().isoformat()
        currency = _extract_currency(ticker_obj)
        display_currency = 'GBP' if currency in ('GBp', 'GBX') else currency

        if catalog_item:
            long_name = catalog_item['name']
            suggested_tax = catalog_item['tax_rate']
        else:
            try:
                info = ticker_obj.info or {}
                long_name = info.get('longName') or info.get('shortName') or clean_ticker
            except Exception:
                long_name = clean_ticker
            suggested_tax = '26.0'

        result = {
            'valid': True,
            'ticker': clean_ticker,
            'name': long_name,
            'currency': display_currency,
            'first_date': first_date,
            'suggested_tax_rate': suggested_tax,
        }
        cache.set(cache_key, result, META_CACHE_TTL)
        return result
    except Exception as exc:
        return {'valid': False, 'error': f'Ticker non valido o errore API ({exc})'}


def fetch_fx_history(currency: str, start_date: str):
    """Scarica e mette in cache la serie storica del cambio {currency}/EUR."""
    if currency == 'EUR':
        return None

    cache_key = f'fx:{currency}:{start_date}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached.copy()

    fx_ticker = f'{currency}EUR=X'
    try:
        df_fx = yf.Ticker(fx_ticker).history(start=start_date, auto_adjust=False)
        if df_fx is None or df_fx.empty:
            df_fx = yf.download(fx_ticker, start=start_date, progress=False, auto_adjust=False)

        if df_fx is None or df_fx.empty:
            return None

        df_fx = _normalize_df_index(df_fx)
        if isinstance(df_fx.columns, pd.MultiIndex):
            if 'Close' in df_fx.columns.get_level_values(0):
                fx_vals = df_fx.xs('Close', axis=1, level=0)
            else:
                fx_vals = df_fx.iloc[:, 0]
        else:
            fx_vals = df_fx['Close'] if 'Close' in df_fx.columns else df_fx.iloc[:, 0]

        if isinstance(fx_vals, pd.DataFrame):
            fx_vals = fx_vals.iloc[:, 0]

        fx_series = pd.to_numeric(fx_vals, errors='coerce').dropna()
        if fx_series.empty:
            return None

        cache.set(cache_key, fx_series, HIST_CACHE_TTL)
        return fx_series.copy()
    except Exception:
        return None


def fetch_ticker_history(ticker: str, start_date: str):
    """
    Scarica la serie storica giornaliera (Close e Dividends) gia convertita in EUR.
    Ritorna (df, currency, error_msg).
    """
    clean_ticker = (ticker or '').upper().strip()
    start_str = str(start_date)
    cache_key = f'hist_eur:{clean_ticker}:{start_str}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached['df'].copy(), cached['currency'], None

    try:
        ticker_obj = yf.Ticker(clean_ticker)
        raw_currency = _extract_currency(ticker_obj)
        df = ticker_obj.history(start=start_str, auto_adjust=False)

        if df is None or df.empty:
            return None, raw_currency, f'Nessun dato storico disponibile per {clean_ticker}.'

        df = _normalize_df_index(df)
        if 'Close' not in df.columns:
            return None, raw_currency, f'Colonna prezzi mancante per {clean_ticker}.'

        if 'Dividends' not in df.columns:
            df['Dividends'] = 0.0

        df = df[['Close', 'Dividends']].copy()
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df['Dividends'] = pd.to_numeric(df['Dividends'], errors='coerce').fillna(0.0)
        df = df.dropna(subset=['Close'])
        df = df[df['Close'] > 0]

        if df.empty:
            return None, raw_currency, f'Serie prezzi non valida per {clean_ticker}.'

        # Gestione titoli UK quotati in pence (GBp / GBX)
        currency = raw_currency
        if currency in ('GBp', 'GBX'):
            df['Close'] = df['Close'] / 100.0
            df['Dividends'] = df['Dividends'] / 100.0
            currency = 'GBP'

        if currency != 'EUR':
            fx_series = fetch_fx_history(currency, start_str)
            if fx_series is None or fx_series.empty:
                return None, currency, f'Cambio {currency}/EUR non disponibile per {clean_ticker}.'
            fx_aligned = fx_series.reindex(df.index).ffill().bfill()
            if fx_aligned.isna().all():
                return None, currency, f'Impossibile allineare il cambio {currency}/EUR per {clean_ticker}.'
            df['Close'] = df['Close'] * fx_aligned
            df['Dividends'] = df['Dividends'] * fx_aligned

        cache.set(cache_key, {'df': df, 'currency': currency}, HIST_CACHE_TTL)
        return df.copy(), currency, None
    except Exception as exc:
        return None, 'EUR', f'Errore durante il download di {clean_ticker}: {exc}'


def compute_xirr(cashflows) -> float | None:
    """
    Calcola il rendimento annuo composto ponderato per i flussi (XIRR / TIR) in %.
    `cashflows` e una lista di tuple (datetime/Timestamp, importo), dove i versamenti
    sono negativi e il valore finale di uscita e positivo.
    """
    if not cashflows or len(cashflows) < 2:
        return None

    # Aggrega eventuali flussi nello stesso giorno
    daily_cf = {}
    for dt, amt in cashflows:
        ts = pd.Timestamp(dt).normalize()
        daily_cf[ts] = daily_cf.get(ts, 0.0) + float(amt)

    items = sorted((ts, amt) for ts, amt in daily_cf.items() if abs(amt) > 1e-9)
    if len(items) < 2:
        return None

    has_neg = any(amt < 0 for _, amt in items)
    has_pos = any(amt > 0 for _, amt in items)
    if not (has_neg and has_pos):
        return None

    d0 = items[0][0]
    total_days = (items[-1][0] - d0).days
    if total_days < 30:
        return None

    times = np.array([(ts - d0).days / 365.25 for ts, _ in items], dtype=float)
    amounts = np.array([amt for _, amt in items], dtype=float)

    def npv(rate: float) -> float:
        base = 1.0 + rate
        if base <= 0:
            return float('inf')
        return float(np.sum(amounts / (base ** times)))

    low, high = -0.99, 10.0
    f_low = npv(low)
    f_high = npv(high)

    # Espandi il limite superiore se necessario (per durate brevi ad altissimo rendimento)
    while f_high > 0 and high < 100.0:
        high *= 2.0
        f_high = npv(high)

    if not (math.isfinite(f_low) and math.isfinite(f_high)) or f_low * f_high > 0:
        return None

    for _ in range(80):
        mid = 0.5 * (low + high)
        f_mid = npv(mid)
        if abs(f_mid) < 1e-7 or (high - low) < 1e-8:
            return round(mid * 100.0, 2)
        if f_mid > 0:
            low = mid
        else:
            high = mid

    return round(0.5 * (low + high) * 100.0, 2)


def simulate_single_pac_from_df(df: pd.DataFrame, dati_input: dict, options: dict | None = None, currency: str = 'EUR'):
    """
    Motore deterministico di simulazione PAC su un singolo DataFrame gia convertito in EUR.
    Separato dall'I/O di yfinance per massima velocita e testabilita.
    """
    if df is None or df.empty:
        return None

    options = options or {}
    reinvest_dividends = bool(options.get('reinvest_dividends', True))
    include_bollo = bool(options.get('include_bollo', True))
    commissione_ordine = max(0.0, float(options.get('commissione_ordine', 0.0) or 0.0))

    ticker = str(dati_input['ticker']).upper().strip()
    rata = max(0.0, float(dati_input.get('importo_periodico', 0.0) or 0.0))
    iniziale = max(0.0, float(dati_input.get('importo_iniziale', 0.0) or 0.0))
    freq = max(1, int(dati_input.get('frequenza', 1) or 1))
    aliquota = float(dati_input.get('aliquota_fiscale', 26.0) or 26.0)
    tax_rate = aliquota / 100.0

    df_clean = df[['Close']].copy()
    df_clean['Dividends'] = df['Dividends'] if 'Dividends' in df.columns else 0.0
    df_clean = df_clean.dropna(subset=['Close'])
    df_clean = df_clean[df_clean['Close'] > 0].sort_index()
    if df_clean.empty:
        return None

    # Date di acquisto periodiche (primo giorno utile di ogni periodo)
    if rata > 0:
        df_mensile = df_clean.resample('MS').first().dropna(subset=['Close'])
        date_acquisto = df_mensile.iloc[::freq].index.to_numpy()
    else:
        date_acquisto = np.array([], dtype='datetime64[ns]')

    dates_idx = df_clean.index
    dates_np = dates_idx.to_numpy()
    years = dates_idx.year.to_numpy()
    closes = df_clean['Close'].to_numpy(dtype=float)
    divs = df_clean['Dividends'].fillna(0.0).to_numpy(dtype=float)
    n = len(closes)

    arr_investito = np.zeros(n, dtype=float)
    arr_valore_mercato = np.zeros(n, dtype=float)
    arr_valore_netto = np.zeros(n, dtype=float)
    arr_valore_lordo = np.zeros(n, dtype=float)
    arr_inflow_net = np.zeros(n, dtype=float)     # Flusso netto immesso nel mercato (per TWRR)
    arr_inflow_gross = np.zeros(n, dtype=float)   # Esborso lordo dell'investitore (per XIRR e annuali)
    arr_div_net = np.zeros(n, dtype=float)        # Dividendi netti del giorno

    quote = 0.0
    costo_fiscale_quote = 0.0
    liquidita = 0.0
    investito_totale = 0.0
    dividendi_lordi_tot = 0.0
    dividendi_netti_tot = 0.0
    tasse_dividendi_tot = 0.0
    bollo_totale = 0.0
    commissioni_tot = 0.0

    # Traccia ombra "Lorda" (0 tasse, 0 bollo, 0 commissioni)
    quote_lordo = 0.0
    liquidita_lordo = 0.0

    next_acq_idx = 0
    num_acq = len(date_acquisto)

    for i in range(n):
        price = closes[i]
        div_unit = divs[i]
        day_gross_buy = 0.0
        day_comm = 0.0

        # A1. Acquisto iniziale al giorno 0
        if i == 0 and iniziale > 0:
            day_gross_buy += iniziale

        # A2. Acquisto PAC programmato
        if next_acq_idx < num_acq and dates_np[i] >= date_acquisto[next_acq_idx]:
            if rata > 0:
                day_gross_buy += rata
            next_acq_idx += 1

        if day_gross_buy > 0:
            # Applica 1 commissione per giornata d'ordine (equa anche al giorno 0)
            comm = min(commissione_ordine, day_gross_buy) if commissione_ordine > 0 else 0.0
            net_buy = max(0.0, day_gross_buy - comm)

            quote += net_buy / price
            costo_fiscale_quote += net_buy
            investito_totale += day_gross_buy
            commissioni_tot += comm
            day_comm = comm

            quote_lordo += day_gross_buy / price

            arr_inflow_gross[i] = day_gross_buy
            arr_inflow_net[i] = net_buy

        # B. Dividendi (se staccati oggi)
        if div_unit > 0 and quote > 0:
            lordo_div = quote * div_unit
            tax_div = lordo_div * tax_rate
            netto_div = lordo_div - tax_div

            dividendi_lordi_tot += lordo_div
            dividendi_netti_tot += netto_div
            tasse_dividendi_tot += tax_div
            arr_div_net[i] = netto_div

            if reinvest_dividends:
                quote += netto_div / price
                # Il dividendo netto e gia stato tassato: incrementa il costo fiscale per evitare doppia tassazione
                costo_fiscale_quote += netto_div
            else:
                liquidita += netto_div

            # Percorso lordo
            lordo_shadow_div = quote_lordo * div_unit
            if reinvest_dividends:
                quote_lordo += lordo_shadow_div / price
            else:
                liquidita_lordo += lordo_shadow_div

        # C. Imposta di bollo (0,20% annuo a fine anno solare)
        if include_bollo and i < n - 1 and years[i] != years[i + 1]:
            val_titoli = quote * price
            if val_titoli > 0:
                bollo = val_titoli * BOLLO_RATE
                bollo_totale += bollo
                if liquidita >= bollo:
                    liquidita -= bollo
                else:
                    shortfall = bollo - liquidita
                    liquidita = 0.0
                    shares_sold = min(quote, shortfall / price)
                    if quote > 0 and shares_sold > 0:
                        ratio_rem = max(0.0, (quote - shares_sold) / quote)
                        costo_fiscale_quote *= ratio_rem
                        quote = max(0.0, quote - shares_sold)

        # D. Valutazioni a fine giornata
        val_asset = quote * price
        val_mercato = val_asset + liquidita
        plus_latente = val_asset - costo_fiscale_quote
        tax_exit_t = plus_latente * tax_rate if plus_latente > 0 else 0.0
        val_netto_t = val_mercato - tax_exit_t
        val_lordo_t = quote_lordo * price + liquidita_lordo

        arr_investito[i] = investito_totale
        arr_valore_mercato[i] = val_mercato
        arr_valore_netto[i] = val_netto_t
        arr_valore_lordo[i] = val_lordo_t

    valore_finale_asset = quote * closes[-1]
    plusvalenza_lorda = valore_finale_asset - costo_fiscale_quote
    tasse_capital_gain = plusvalenza_lorda * tax_rate if plusvalenza_lorda > 0 else 0.0
    plusvalenza_netta = plusvalenza_lorda - tasse_capital_gain

    valore_netto_finale = float(arr_valore_netto[-1])
    valore_lordo_finale = float(arr_valore_lordo[-1])
    profitto_netto_totale = valore_netto_finale - investito_totale
    tasse_e_costi_tot = tasse_capital_gain + tasse_dividendi_tot + bollo_totale + commissioni_tot

    serie_storica = pd.DataFrame(
        {
            'investito': arr_investito,
            'valore_mercato': arr_valore_mercato,
            'valore_netto': arr_valore_netto,
            'valore_lordo': arr_valore_lordo,
            'inflow_net': arr_inflow_net,
            'inflow_gross': arr_inflow_gross,
            'div_net': arr_div_net,
        },
        index=dates_idx,
    )

    catalog_item = get_catalog_entry(ticker)
    return {
        'ticker': ticker,
        'name': catalog_item['name'] if catalog_item else ticker,
        'currency': 'GBP' if currency in ('GBp', 'GBX') else currency,
        'aliquota': aliquota,
        'serie_storica': serie_storica,
        'investito': investito_totale,
        'valore_asset': valore_finale_asset,
        'valore_netto': valore_netto_finale,
        'valore_lordo': valore_lordo_finale,
        'dividendi_lordi': dividendi_lordi_tot,
        'dividendi_netti': dividendi_netti_tot,
        'tasse_dividendi': tasse_dividendi_tot,
        'plusvalenza_lorda': plusvalenza_lorda,
        'plusvalenza_netta': plusvalenza_netta,
        'tasse_capital_gain': tasse_capital_gain,
        'bollo': bollo_totale,
        'commissioni': commissioni_tot,
        'tasse': tasse_e_costi_tot,
        'profitto_netto': profitto_netto_totale,
    }


def _aggregate_series(lista_risultati: list[dict]) -> pd.DataFrame:
    """Allinea e somma le serie temporali multi-ETF lungo un unico calendario."""
    stock_cols = ['investito', 'valore_mercato', 'valore_netto', 'valore_lordo']
    flow_cols = ['inflow_net', 'inflow_gross', 'div_net']

    frames_stock = []
    frames_flow = []
    for idx, res in enumerate(lista_risultati):
        s = res['serie_storica']
        frames_stock.append(s[stock_cols].rename(columns={c: f'{c}__{idx}' for c in stock_cols}))
        frames_flow.append(s[flow_cols].rename(columns={c: f'{c}__{idx}' for c in flow_cols}))

    df_stock = pd.concat(frames_stock, axis=1).sort_index().ffill().fillna(0.0)
    df_flow = pd.concat(frames_flow, axis=1).sort_index().fillna(0.0)

    out = pd.DataFrame(index=df_stock.index)
    for col in stock_cols:
        cols = [c for c in df_stock.columns if c.startswith(f'{col}__')]
        out[col] = df_stock[cols].sum(axis=1)
    for col in flow_cols:
        cols = [c for c in df_flow.columns if c.startswith(f'{col}__')]
        out[col] = df_flow[cols].sum(axis=1)

    return out


def _compute_drawdowns(series_val: pd.Series):
    """Calcola la serie underwater (%) e i Top 5 drawdown con tempi di recupero."""
    if series_val.empty:
        return pd.Series(dtype=float), []

    rolling_max = series_val.cummax()
    with np.errstate(divide='ignore', invalid='ignore'):
        dd_pct = np.where(rolling_max > 0, (series_val - rolling_max) / rolling_max * 100.0, 0.0)
    dd_series = pd.Series(dd_pct, index=series_val.index).fillna(0.0)

    is_underwater = dd_series < -1e-9
    groups = dd_series[is_underwater].groupby((~is_underwater).cumsum())

    dd_list = []
    for _, group in groups:
        if group.empty:
            continue
        trough_date = group.idxmin()
        depth_pct = float(group.min())
        peak_val = float(rolling_max.loc[trough_date])

        history_slice = series_val.loc[:trough_date]
        peak_candidates = history_slice[history_slice >= peak_val * 0.99999]
        peak_date = peak_candidates.last_valid_index()
        if peak_date is None:
            continue

        peak_val_real = float(series_val.loc[peak_date])
        trough_val = float(series_val.loc[trough_date])
        loss_euro = trough_val - peak_val_real

        # Cerca la data di recupero (primo giorno dopo il trough con dd == 0)
        after_trough = dd_series.loc[trough_date:]
        recovered = after_trough[after_trough >= -1e-9]
        if not recovered.empty:
            recovery_date = recovered.index[0]
            recovery_days = int((recovery_date - peak_date).days)
            recovery_label = f'{recovery_days} gg ({recovery_date.strftime("%d/%m/%y")})'
        else:
            recovery_days = None
            recovery_label = 'In corso'

        dd_list.append({
            'pct': round(depth_pct, 2),
            'euro': round(loss_euro, 2),
            'peak_date': peak_date,
            'trough_date': trough_date,
            'period': f"{peak_date.strftime('%d/%m/%y')} - {trough_date.strftime('%d/%m/%y')}",
            'drop_days': int((trough_date - peak_date).days),
            'recovery_days': recovery_days,
            'recovery_label': recovery_label,
        })

    dd_list.sort(key=lambda x: x['pct'])
    return dd_series, dd_list[:5]


def _compute_daily_twrr(val_mercato: pd.Series, inflow_net: pd.Series) -> pd.Series:
    """Calcola i rendimenti giornalieri Time-Weighted escludendo l'effetto dei versamenti."""
    vals = val_mercato.to_numpy(dtype=float)
    flows = inflow_net.to_numpy(dtype=float)
    rets = np.zeros(len(vals), dtype=float)
    for i in range(1, len(vals)):
        prev = vals[i - 1]
        if prev > 0:
            rets[i] = (vals[i] - flows[i]) / prev - 1.0
    return pd.Series(rets, index=val_mercato.index)


def _downsample_chart_df(df_chart: pd.DataFrame, preserve_dates: list, max_points: int = 450) -> pd.DataFrame:
    """Riduce i punti per Chart.js preservando inizio, fine e picco/fondo del max drawdown."""
    if len(df_chart) <= max_points:
        return df_chart

    step = max(1, len(df_chart) // max_points)
    keep_idx = set(df_chart.index[::step])
    keep_idx.add(df_chart.index[0])
    keep_idx.add(df_chart.index[-1])
    for dt in preserve_dates:
        if dt in df_chart.index:
            keep_idx.add(dt)

    return df_chart.loc[sorted(keep_idx)]


def calcola_singolo_pac(dati_input: dict, options: dict | None = None):
    """Scarica i dati di un ETF ed esegue la simulazione PAC."""
    ticker = (dati_input.get('ticker') or '').upper().strip()
    start_date = str(dati_input.get('data_inizio', '2018-01-01'))
    df, currency, err = fetch_ticker_history(ticker, start_date)
    if df is None:
        return {'_error': err or f'Dati non disponibili per {ticker}'}
    res = simulate_single_pac_from_df(df, dati_input, options=options, currency=currency)
    if res is None:
        return {'_error': f'Impossibile simulare {ticker} nel periodo selezionato.'}
    res['_df'] = df
    return res


def calcola_portafoglio_pac(lista_input: list[dict], options: dict | None = None):
    """
    Esegue il backtest completo multi-ETF con download parallelo, metriche quantitative,
    confronto PAC vs PIC, analisi drawdown e riepilogo annuale.
    """
    if not lista_input:
        return {'error': 'Nessun ETF configurato per la simulazione.'}

    options = options or {
        'reinvest_dividends': True,
        'include_bollo': True,
        'commissione_ordine': 0.0,
    }

    risultati_singoli = []
    warnings = []

    with ThreadPoolExecutor(max_workers=min(4, len(lista_input))) as pool:
        results_raw = list(pool.map(lambda inp: calcola_singolo_pac(inp, options), lista_input))

    valid_pairs = []
    for inp, res in zip(lista_input, results_raw):
        if res is None:
            warnings.append(f"Impossibile elaborare {inp.get('ticker', '?')}.")
        elif '_error' in res:
            warnings.append(res['_error'])
        else:
            risultati_singoli.append(res)
            valid_pairs.append((inp, res))

    if not risultati_singoli:
        return {
            'error': warnings[0] if warnings else 'Nessun dato valido trovato per gli ETF selezionati.',
            'warnings': warnings,
        }

    df_totale = _aggregate_series(risultati_singoli)
    dates_idx = df_totale.index

    # --- METRICHE DI PORTAFOGLIO ---
    investito_tot = sum(r['investito'] for r in risultati_singoli)
    dividendi_lordi_tot = sum(r['dividendi_lordi'] for r in risultati_singoli)
    dividendi_netti_tot = sum(r['dividendi_netti'] for r in risultati_singoli)
    tasse_dividendi_tot = sum(r['tasse_dividendi'] for r in risultati_singoli)
    plusvalenza_lorda_tot = sum(r['plusvalenza_lorda'] for r in risultati_singoli)
    plusvalenza_netta_tot = sum(r['plusvalenza_netta'] for r in risultati_singoli)
    tasse_cap_gain_tot = sum(r['tasse_capital_gain'] for r in risultati_singoli)
    bollo_tot = sum(r['bollo'] for r in risultati_singoli)
    commissioni_tot = sum(r['commissioni'] for r in risultati_singoli)
    tasse_e_costi_tot = tasse_cap_gain_tot + tasse_dividendi_tot + bollo_tot + commissioni_tot

    valore_netto_finale = float(df_totale['valore_netto'].iloc[-1])
    valore_lordo_finale = float(df_totale['valore_lordo'].iloc[-1])
    profitto_netto_tot = valore_netto_finale - investito_tot
    profitto_lordo_tot = valore_lordo_finale - investito_tot

    roi_netto_pct = (profitto_netto_tot / investito_tot * 100.0) if investito_tot > 0 else 0.0
    roi_lordo_pct = (profitto_lordo_tot / investito_tot * 100.0) if investito_tot > 0 else 0.0

    # --- XIRR NETTO ---
    cashflows_pac = []
    inflows_gross = df_totale['inflow_gross']
    for dt, amt in inflows_gross[inflows_gross > 0].items():
        cashflows_pac.append((dt, -float(amt)))
    cashflows_pac.append((dates_idx[-1], valore_netto_finale))
    xirr_netto_pct = compute_xirr(cashflows_pac)

    durata_giorni = max(1, int((dates_idx[-1] - dates_idx[0]).days))
    durata_anni = round(durata_giorni / 365.25, 1)

    # --- VOLATILITA ANNUALIZZATA (TWRR) ---
    daily_twrr = _compute_daily_twrr(df_totale['valore_mercato'], df_totale['inflow_net'])
    active_rets = daily_twrr.iloc[1:]
    volatilita_annua = round(float(active_rets.std(ddof=1) * np.sqrt(252) * 100.0), 2) if len(active_rets) > 2 else 0.0

    # --- DRAWDOWN SU VALORE DI MERCATO ---
    dd_series, top_5_drawdowns = _compute_drawdowns(df_totale['valore_mercato'])
    max_drawdown_pct = top_5_drawdowns[0]['pct'] if top_5_drawdowns else 0.0
    max_drawdown_euro = top_5_drawdowns[0]['euro'] if top_5_drawdowns else 0.0

    # --- CONFRONTO PAC vs PIC (LUMP SUM) ---
    pic_risultati = []
    for inp, res in valid_pairs:
        pic_inp = {
            'ticker': inp['ticker'],
            'data_inizio': inp['data_inizio'],
            'importo_iniziale': res['investito'],
            'importo_periodico': 0.0,
            'frequenza': 1,
            'aliquota_fiscale': inp.get('aliquota_fiscale', '26.0'),
        }
        pic_res = simulate_single_pac_from_df(res['_df'], pic_inp, options=options, currency=res['currency'])
        if pic_res:
            pic_risultati.append(pic_res)

    if pic_risultati:
        df_pic = _aggregate_series(pic_risultati).reindex(dates_idx).ffill().fillna(0.0)
        pic_valore_netto = float(df_pic['valore_netto'].iloc[-1])
        pic_profitto_netto = pic_valore_netto - investito_tot
        pic_roi_netto_pct = (pic_profitto_netto / investito_tot * 100.0) if investito_tot > 0 else 0.0

        cf_pic = []
        pic_inflows = df_pic['inflow_gross']
        for dt, amt in pic_inflows[pic_inflows > 0].items():
            cf_pic.append((dt, -float(amt)))
        cf_pic.append((dates_idx[-1], pic_valore_netto))
        pic_xirr_pct = compute_xirr(cf_pic)

        _, pic_dds = _compute_drawdowns(df_pic['valore_mercato'])
        pic_max_dd_pct = pic_dds[0]['pct'] if pic_dds else 0.0
        pic_series = df_pic['valore_netto']
    else:
        pic_valore_netto = 0.0
        pic_roi_netto_pct = 0.0
        pic_xirr_pct = None
        pic_max_dd_pct = 0.0
        pic_series = pd.Series(0.0, index=dates_idx)

    # --- RIEPILOGO ANNUALE ---
    riepilogo_annuale = []
    df_years = pd.DataFrame({
        'year': dates_idx.year,
        'inflow_gross': df_totale['inflow_gross'],
        'valore_netto': df_totale['valore_netto'],
        'investito': df_totale['investito'],
        'div_net': df_totale['div_net'],
        'twrr': daily_twrr,
    }, index=dates_idx)

    for anno, grp in df_years.groupby('year'):
        twrr_vals = grp['twrr'].to_numpy(dtype=float)
        year_twrr_pct = (float(np.prod(1.0 + twrr_vals)) - 1.0) * 100.0
        riepilogo_annuale.append({
            'anno': int(anno),
            'versato_anno': round(float(grp['inflow_gross'].sum()), 2),
            'versato_cumulato': round(float(grp['investito'].iloc[-1]), 2),
            'valore_fine_anno': round(float(grp['valore_netto'].iloc[-1]), 2),
            'dividendi_anno': round(float(grp['div_net'].sum()), 2),
            'variazione_pct': round(year_twrr_pct, 2),
        })

    # --- ALLOCAZIONE FINALE ---
    tot_val_netto_singoli = sum(max(0.0, r['valore_netto']) for r in risultati_singoli)
    allocazione = []
    for r in risultati_singoli:
        weight = (max(0.0, r['valore_netto']) / tot_val_netto_singoli * 100.0) if tot_val_netto_singoli > 0 else 0.0
        r['peso_pct'] = round(weight, 1)
        r['roi_pct'] = round((r['profitto_netto'] / r['investito'] * 100.0), 2) if r['investito'] > 0 else 0.0
        allocazione.append({
            'ticker': r['ticker'],
            'name': r['name'],
            'peso_pct': r['peso_pct'],
            'valore_netto': round(r['valore_netto'], 2),
        })
        # Rimuovi riferimenti pesanti al DataFrame dai risultati passati al template
        r.pop('_df', None)
        r.pop('serie_storica', None)

    # --- SERIE GRAFICI ---
    df_chart = pd.DataFrame({
        'valore': df_totale['valore_netto'],
        'valore_lordo': df_totale['valore_lordo'],
        'investito': df_totale['investito'],
        'pic_valore': pic_series,
        'drawdown': dd_series,
    }, index=dates_idx)

    preserve = []
    if top_5_drawdowns:
        preserve.extend([top_5_drawdowns[0]['peak_date'], top_5_drawdowns[0]['trough_date']])
    df_chart_ds = _downsample_chart_df(df_chart, preserve)

    storico_grafico = [
        {
            'date': dt.strftime('%Y-%m-%d'),
            'valore': round(float(row['valore']), 2),
            'valore_lordo': round(float(row['valore_lordo']), 2),
            'investito': round(float(row['investito']), 2),
            'pic_valore': round(float(row['pic_valore']), 2),
            'drawdown': round(float(row['drawdown']), 2),
        }
        for dt, row in df_chart_ds.iterrows()
    ]

    # Pulisci date datetime da top_5_drawdowns prima di serializzare/passare
    for dd in top_5_drawdowns:
        dd.pop('peak_date', None)
        dd.pop('trough_date', None)

    return {
        'warnings': warnings,
        'options': {
            'reinvest_dividends': bool(options.get('reinvest_dividends', True)),
            'include_bollo': bool(options.get('include_bollo', True)),
            'commissione_ordine': round(float(options.get('commissione_ordine', 0.0) or 0.0), 2),
        },
        'dettagli_singoli': risultati_singoli,
        'allocazione': allocazione,
        'investito': round(investito_tot, 2),
        'dividendi_lordi': round(dividendi_lordi_tot, 2),
        'dividendi_netti': round(dividendi_netti_tot, 2),
        'tasse_dividendi': round(tasse_dividendi_tot, 2),
        'plusvalenza_lorda': round(plusvalenza_lorda_tot, 2),
        'plusvalenza_netta': round(plusvalenza_netta_tot, 2),
        'tasse_capital_gain': round(tasse_cap_gain_tot, 2),
        'bollo_totale': round(bollo_tot, 2),
        'commissioni_totale': round(commissioni_tot, 2),
        'tasse': round(tasse_e_costi_tot, 2),
        'valore_netto': round(valore_netto_finale, 2),
        'valore_finale_lordo': round(valore_lordo_finale, 2),
        'profitto_netto': round(profitto_netto_tot, 2),
        'profitto_lordo': round(profitto_lordo_tot, 2),
        'profitto_pct': round(roi_netto_pct, 2),
        'roi_lordo_pct': round(roi_lordo_pct, 2),
        'xirr_netto_pct': xirr_netto_pct,
        'durata_anni': durata_anni,
        'volatilita_annua': volatilita_annua,
        'max_drawdown_pct': max_drawdown_pct,
        'max_drawdown_euro': max_drawdown_euro,
        'top_drawdowns': top_5_drawdowns,
        'pic': {
            'valore_netto': round(pic_valore_netto, 2),
            'roi_netto_pct': round(pic_roi_netto_pct, 2),
            'xirr_pct': pic_xirr_pct,
            'max_drawdown_pct': pic_max_dd_pct,
            'differenza_euro': round(valore_netto_finale - pic_valore_netto, 2),
        },
        'riepilogo_annuale': riepilogo_annuale,
        'storico_grafico': storico_grafico,
    }
