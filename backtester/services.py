import numpy as np
import pandas as pd
import yfinance as yf


def calcola_singolo_pac(dati_input):
    """Calcola il PAC per un singolo ETF e restituisce un DataFrame con la serie storica."""
    ticker = dati_input['ticker']
    start_date = dati_input['data_inizio']
    rata = dati_input['importo_periodico']
    iniziale = dati_input.get('importo_iniziale', 0)
    freq = int(dati_input['frequenza'])

    # 1. Download Dati
    try:
        # FIX: auto_adjust=False per ripristinare il comportamento classico
        df = yf.download(ticker, start=start_date, progress=False, auto_adjust=False)
        if df.empty:
            return None

        # Gestione robusta delle colonne
        price_series = None

        if isinstance(df.columns, pd.MultiIndex):
            if 'Adj Close' in df.columns.get_level_values(0):
                price_series = df['Adj Close']
            elif 'Close' in df.columns.get_level_values(0):
                price_series = df['Close']
        else:
            if 'Adj Close' in df.columns:
                price_series = df['Adj Close']
            elif 'Close' in df.columns:
                price_series = df['Close']

        if price_series is None:
            price_series = df.iloc[:, 0]

        df = price_series

        if isinstance(df, pd.DataFrame):
            df = df.iloc[:, 0]

    except Exception as e:
        print(f"Errore download {ticker}: {e}")
        return None

    # 2. Date di acquisto
    df_mensile = df.resample('MS').first()
    date_acquisto = df_mensile.iloc[::freq]

    # 3. Simulazione
    quote_totali = 0
    investito_totale = 0

    # DataFrame per tracciare l'evoluzione giornaliera
    # Inizializziamo con dtype float per stabilità
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
        'serie_storica': serie_storica,
        'investito': serie_storica.iloc[-1]['investito'],
        'valore_finale': valore_finale,
        'tasse': tasse,
        'profitto_netto': profitto - tasse
    }


def calcola_portafoglio_pac(lista_input):
    """
    Riceve una LISTA di dizionari input.
    Aggrega le serie storiche e restituisce il totale.
    """
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

    # Forward Fill sul totale aggregato
    df_totale = df_totale.ffill().fillna(0)

    # FIX CRASH SINGOLO ETF:
    # Se c'è un solo ETF, df_totale['investito'] è una Series (non ha axis=1).
    # Se ci sono più ETF, è un DataFrame.

    subset_investito = df_totale['investito']
    if isinstance(subset_investito, pd.DataFrame):
        df_investito = subset_investito.sum(axis=1)
    else:
        df_investito = subset_investito  # È già la serie corretta

    subset_valore = df_totale['valore']
    if isinstance(subset_valore, pd.DataFrame):
        df_valore = subset_valore.sum(axis=1)
    else:
        df_valore = subset_valore

    # Calcolo Max Drawdown
    rolling_max = df_valore.cummax()
    # Evitiamo divisione per zero se il valore è 0 all'inizio
    with np.errstate(divide='ignore', invalid='ignore'):
        drawdown = (df_valore - rolling_max) / rolling_max

    drawdown = drawdown.fillna(0)  # Fix per NaN iniziali
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
