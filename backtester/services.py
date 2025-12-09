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
        df = yf.download(ticker, start=start_date, progress=False)
        if df.empty: return None

        # Gestione colonne MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df = df['Adj Close']
        elif 'Adj Close' in df.columns:
            df = df['Adj Close']
        else:
            df = df['Close']

        # Pulizia: se ci sono più colonne (es. ticker duplicati), prendiamo la prima
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
    # Creiamo una serie vuota indicizzata con le date del download
    serie_storica = pd.DataFrame(index=df.index, columns=['investito', 'valore'])

    # Acquisto Iniziale
    first_price = date_acquisto.iloc[0] if not date_acquisto.empty else None
    if iniziale > 0 and first_price and not pd.isna(first_price):
        quote_totali += iniziale / first_price
        investito_totale += iniziale

    # Loop acquisti periodici
    # Usiamo un iteratore per gestire lo stato progressivo
    next_acquisto_idx = 0
    date_acq_list = date_acquisto.index.tolist()

    for data in df.index:
        # Se oggi è (o è passato) il giorno di un acquisto, compriamo
        # (Logica semplificata: se la data corrente match la data di acquisto ricampionata)
        if next_acquisto_idx < len(date_acq_list) and data >= date_acq_list[next_acquisto_idx]:
            prezzo_acquisto = df.loc[data]  # Prezzo di oggi
            if not pd.isna(prezzo_acquisto):
                quote_totali += rata / prezzo_acquisto
                investito_totale += rata
                next_acquisto_idx += 1

        # Aggiorniamo il valore corrente
        if not pd.isna(df.loc[data]):
            valore_corrente = quote_totali * df.loc[data]
            serie_storica.loc[data] = [investito_totale, valore_corrente]

    # Riempiamo eventuali buchi (forward fill)
    serie_storica = serie_storica.ffill().fillna(0)

    # Calcoli finali per questo ETF
    valore_finale = serie_storica.iloc[-1]['valore']
    profitto = valore_finale - serie_storica.iloc[-1]['investito']
    tasse = profitto * 0.26 if profitto > 0 else 0

    return {
        'ticker': ticker,
        'serie_storica': serie_storica,  # DataFrame Pandas
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
    # Uniamo tutti i dataframe allineandoli sulle date
    df_totale = pd.concat(serie_aggregate, axis=1)

    # Sommiamo le colonne 'investito' e 'valore' di tutti gli ETF
    # Nota: il concat crea colonne duplicate 'investito', 'valore'.
    # Dobbiamo sommare trasversalmente.
    df_investito = df_totale['investito'].sum(axis=1)
    df_valore = df_totale['valore'].sum(axis=1)

    # Calcolo Max Drawdown sul Portafoglio Totale
    rolling_max = df_valore.cummax()
    drawdown = (df_valore - rolling_max) / rolling_max
    max_dd = drawdown.min() * 100

    # Preparazione dati per grafico (JSON friendly)
    storico_grafico = []
    for data, valore in df_valore.items():
        # Saltiamo i giorni dove il valore è 0 (prima dell'inizio)
        if valore > 0:
            storico_grafico.append({
                'date': data.strftime('%Y-%m-%d'),
                'valore': round(valore, 2),
                'investito': round(df_investito.loc[data], 2)
            })

    # Totali Generali
    investito_tot = sum(r['investito'] for r in risultati_singoli)
    valore_fin_tot = sum(r['valore_finale'] for r in risultati_singoli)
    tasse_tot = sum(r['tasse'] for r in
                    risultati_singoli)  # Tasse calcolate su ogni singolo ETF (gestione minusvalenze esclusa per prudenza)
    profitto_netto_tot = sum(r['profitto_netto'] for r in risultati_singoli)

    return {
        'dettagli_singoli': risultati_singoli,  # Per tabella dettaglio
        'investito': round(investito_tot, 2),
        'valore_finale': round(valore_fin_tot, 2),
        'valore_netto': round(investito_tot + profitto_netto_tot, 2),
        'profitto_pct': round((profitto_netto_tot / investito_tot * 100), 2) if investito_tot > 0 else 0,
        'tasse': round(tasse_tot, 2),
        'max_drawdown': round(max_dd, 2),
        'storico_grafico': storico_grafico
    }
