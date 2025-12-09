import numpy as np
import pandas as pd
import yfinance as yf


def get_clean_series(df, col_name='Adj Close'):
    """Helper per estrarre una serie pulita da yfinance, gestendo MultiIndex e colonne."""
    if df.empty:
        return None

    series = None
    # Caso MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        if col_name in df.columns.get_level_values(0):
            series = df[col_name]
        elif 'Close' in df.columns.get_level_values(0):
            series = df['Close']
    # Caso Flat Index
    else:
        if col_name in df.columns:
            series = df[col_name]
        elif 'Close' in df.columns:
            series = df['Close']

    # Fallback brutale
    if series is None:
        series = df.iloc[:, 0]

    # Se dopo l'estrazione è ancora un DataFrame (es. ticker duplicati), prendiamo la prima colonna
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]

    return series


def calcola_singolo_pac(dati_input):
    """Calcola il PAC per un singolo ETF convertendo tutto in EURO."""
    ticker = dati_input['ticker']
    start_date = dati_input['data_inizio']
    rata = dati_input['importo_periodico']
    iniziale = dati_input.get('importo_iniziale', 0)
    freq = int(dati_input['frequenza'])

    # 1. Identifica Valuta
    currency = 'EUR'
    try:
        # fast_info è rapido e non conta come chiamata API pesante
        ticker_obj = yf.Ticker(ticker)
        currency = ticker_obj.fast_info.get('currency', 'EUR')
    except Exception:
        pass  # Se fallisce assumiamo EUR

    # 2. Download Dati ETF
    try:
        df = yf.download(ticker, start=start_date, progress=False, auto_adjust=False)
        price_series = get_clean_series(df)
        if price_series is None: return None

        # 3. Conversione Valuta (Se necessaria)
        if currency != 'EUR':
            # Costruiamo il ticker del cambio, es: 'USDEUR=X'
            fx_ticker = f"{currency}EUR=X"

            # Scarichiamo storico cambio
            df_fx = yf.download(fx_ticker, start=start_date, progress=False, auto_adjust=False)
            fx_series = get_clean_series(df_fx)

            if fx_series is not None:
                # Allineiamo il cambio alle date dell'ETF
                # Usiamo 'ffill' perché il forex non chiude come la borsa azionaria,
                # ma vogliamo assicurarci di avere un tasso per ogni giorno di trading dell'ETF.
                fx_series = fx_series.reindex(price_series.index, method='ffill').fillna(method='bfill')

                # Convertiamo il prezzo in EURO
                price_series = price_series * fx_series

        # Usiamo la serie convertita come base
        df = price_series

    except Exception as e:
        print(f"Errore calcolo {ticker}: {e}")
        return None

    # 4. Date di acquisto
    df_mensile = df.resample('MS').first()
    date_acquisto = df_mensile.iloc[::freq]

    # 5. Simulazione
    quote_totali = 0
    investito_totale = 0

    serie_storica = pd.DataFrame(index=df.index, columns=['investito', 'valore'], dtype=float)

    # Acquisto Iniziale
    first_price = date_acquisto.iloc[0] if not date_acquisto.empty else None
    if iniziale > 0 and first_price and not pd.isna(first_price):
        quote_totali += iniziale / first_price
        investito_totale += iniziale

    # Loop acquisti periodici
    next_acquisto_idx = 0
    date_acq_list = date_acquisto.index.tolist()

    for data in df.index:
        if next_acquisto_idx < len(date_acq_list) and data >= date_acq_list[next_acquisto_idx]:
            prezzo_acquisto = df.loc[data]
            if not pd.isna(prezzo_acquisto):
                quote_totali += rata / prezzo_acquisto
                investito_totale += rata
                next_acquisto_idx += 1

        if not pd.isna(df.loc[data]):
            valore_corrente = quote_totali * df.loc[data]
            serie_storica.loc[data] = [investito_totale, valore_corrente]

    serie_storica = serie_storica.ffill().fillna(0)

    valore_finale = serie_storica.iloc[-1]['valore']
    profitto = valore_finale - serie_storica.iloc[-1]['investito']
    tasse = profitto * 0.26 if profitto > 0 else 0

    return {
        'ticker': ticker,
        'currency': currency,  # Info utile per debug
        'serie_storica': serie_storica,
        'investito': serie_storica.iloc[-1]['investito'],
        'valore_finale': valore_finale,
        'tasse': tasse,
        'profitto_netto': profitto - tasse
    }


def calcola_portafoglio_pac(lista_input):
    """Aggrega le serie storiche convertite in EURO e restituisce il totale."""
    risultati_singoli = []
    serie_aggregate = []

    for input_pac in lista_input:
        res = calcola_singolo_pac(input_pac)
        if res:
            risultati_singoli.append(res)
            serie_aggregate.append(res['serie_storica'])

    if not risultati_singoli:
        return None

    # --- AGGREGAZIONE ---
    df_totale = pd.concat(serie_aggregate, axis=1)
    df_totale = df_totale.ffill().fillna(0)

    subset_investito = df_totale['investito']
    if isinstance(subset_investito, pd.DataFrame):
        df_investito = subset_investito.sum(axis=1)
    else:
        df_investito = subset_investito

    subset_valore = df_totale['valore']
    if isinstance(subset_valore, pd.DataFrame):
        df_valore = subset_valore.sum(axis=1)
    else:
        df_valore = subset_valore

    # Calcolo Max Drawdown
    rolling_max = df_valore.cummax()
    with np.errstate(divide='ignore', invalid='ignore'):
        drawdown = (df_valore - rolling_max) / rolling_max

    drawdown = drawdown.fillna(0)
    max_dd = drawdown.min() * 100

    storico_grafico = []
    for data, valore in df_valore.items():
        if valore > 0:
            storico_grafico.append({
                'date': data.strftime('%Y-%m-%d'),
                'valore': round(valore, 2),
                'investito': round(df_investito.loc[data], 2)
            })

    investito_tot = sum(r['investito'] for r in risultati_singoli)
    valore_fin_tot = sum(r['valore_finale'] for r in risultati_singoli)
    tasse_tot = sum(r['tasse'] for r in risultati_singoli)
    profitto_netto_tot = sum(r['profitto_netto'] for r in risultati_singoli)

    return {
        'dettagli_singoli': risultati_singoli,
        'investito': round(investito_tot, 2),
        'valore_finale': round(valore_fin_tot, 2),
        'valore_netto': round(investito_tot + profitto_netto_tot, 2),
        'profitto_pct': round((profitto_netto_tot / investito_tot * 100), 2) if investito_tot > 0 else 0,
        'tasse': round(tasse_tot, 2),
        'max_drawdown': round(max_dd, 2),
        'storico_grafico': storico_grafico
    }
