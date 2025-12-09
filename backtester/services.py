import numpy as np
import pandas as pd
import yfinance as yf


def calcola_singolo_pac(dati_input):
    """
    Calcola il PAC separando il valore delle quote dalla liquidità generata dai dividendi.
    """
    ticker = dati_input['ticker']
    start_date = dati_input['data_inizio']
    rata = dati_input['importo_periodico']
    iniziale = dati_input.get('importo_iniziale', 0)
    freq = int(dati_input['frequenza'])

    # 1. Identifica Valuta e Scarica Dati
    currency = 'EUR'
    try:
        ticker_obj = yf.Ticker(ticker)
        try:
            currency = ticker_obj.fast_info.get('currency', 'EUR')
        except:
            currency = ticker_obj.info.get('currency', 'EUR')

        # SCARICHIAMO LO STORICO COMPLETO
        df = ticker_obj.history(start=start_date, auto_adjust=False)

        if df.empty: return None

        # Pulizia Timezone
        df.index = df.index.tz_localize(None)

        # Gestione Cambio Valuta
        fx_series = None
        if currency != 'EUR':
            fx_ticker = f"{currency}EUR=X"
            df_fx = yf.download(fx_ticker, start=start_date, progress=False, auto_adjust=False)

            # FIX ROBUSTEZZA COLONNE FX
            fx_vals = None
            if isinstance(df_fx.columns, pd.MultiIndex):
                if 'Close' in df_fx.columns.get_level_values(0):
                    fx_vals = df_fx.xs('Close', axis=1, level=0)
                elif 'Adj Close' in df_fx.columns.get_level_values(0):
                    fx_vals = df_fx.xs('Adj Close', axis=1, level=0)
            else:
                if 'Close' in df_fx.columns:
                    fx_vals = df_fx['Close']
                elif 'Adj Close' in df_fx.columns:
                    fx_vals = df_fx['Adj Close']

            if fx_vals is None:
                fx_vals = df_fx.iloc[:, 0]

            if isinstance(fx_vals, pd.DataFrame):
                fx_vals = fx_vals.iloc[:, 0]

            fx_series = fx_vals.reindex(df.index).ffill().bfill()

            df['Close'] = df['Close'] * fx_series
            if 'Dividends' in df.columns:
                df['Dividends'] = df['Dividends'] * fx_series

    except Exception as e:
        print(f"Errore calcolo {ticker}: {e}")
        return None

    # 2. Date di acquisto
    df_mensile = df.resample('MS').first()
    date_acquisto = df_mensile.iloc[::freq].index

    # 3. Simulazione
    quote_totali = 0
    investito_totale = 0
    dividendi_lordi_tot = 0
    dividendi_netti_tot = 0
    tasse_dividendi_pagate = 0

    serie_storica = pd.DataFrame(index=df.index, columns=['investito', 'valore', 'liquidita'], dtype=float)

    # Acquisto Iniziale
    first_idx = df.index[0]
    first_price = df.loc[first_idx, 'Close']

    if iniziale > 0 and not pd.isna(first_price):
        quote_totali += iniziale / first_price
        investito_totale += iniziale

    next_acq_idx = 0

    for data, row in df.iterrows():
        # A. Acquisto PAC
        if next_acq_idx < len(date_acquisto) and data >= date_acquisto[next_acq_idx]:
            prezzo_acquisto = row['Close']
            if not pd.isna(prezzo_acquisto) and prezzo_acquisto > 0:
                quote_totali += rata / prezzo_acquisto
                investito_totale += rata
                next_acq_idx += 1

        # B. Dividendi
        div_unitario = row.get('Dividends', 0)
        if div_unitario > 0 and quote_totali > 0:
            lordo = quote_totali * div_unitario
            tax = lordo * 0.26
            netto = lordo - tax

            dividendi_lordi_tot += lordo
            dividendi_netti_tot += netto
            tasse_dividendi_pagate += tax

        # C. Serie Storica
        valore_asset = quote_totali * row['Close']
        serie_storica.loc[data] = [investito_totale, valore_asset, dividendi_netti_tot]

    serie_storica = serie_storica.ffill().fillna(0)

    # Calcoli finali
    last_row = serie_storica.iloc[-1]
    valore_finale_asset = last_row['valore']

    plusvalenza_lorda = valore_finale_asset - investito_totale
    tasse_capital_gain = plusvalenza_lorda * 0.26 if plusvalenza_lorda > 0 else 0
    plusvalenza_netta = plusvalenza_lorda - tasse_capital_gain

    valore_netto_totale = investito_totale + plusvalenza_netta + dividendi_netti_tot
    profitto_netto_totale = valore_netto_totale - investito_totale
    tasse_totali = tasse_capital_gain + tasse_dividendi_pagate

    return {
        'ticker': ticker,
        'currency': currency,
        'serie_storica': serie_storica,
        'investito': investito_totale,
        'valore_asset': valore_finale_asset,
        'dividendi_lordi': dividendi_lordi_tot,
        'dividendi_netti': dividendi_netti_tot,
        'plusvalenza_lorda': plusvalenza_lorda,
        'plusvalenza_netta': plusvalenza_netta,
        'tasse': tasse_totali,
        'profitto_netto': profitto_netto_totale,
        'valore_netto': valore_netto_totale
    }


def calcola_portafoglio_pac(lista_input):
    risultati_singoli = []
    serie_aggregate = []

    for input_pac in lista_input:
        res = calcola_singolo_pac(input_pac)
        if res:
            risultati_singoli.append(res)
            serie_aggregate.append(res['serie_storica'])

    if not risultati_singoli: return None

    df_totale = pd.concat(serie_aggregate, axis=1)
    df_totale = df_totale.ffill().fillna(0)

    def safe_sum(df, col_name):
        subset = df[col_name]
        return subset.sum(axis=1) if isinstance(subset, pd.DataFrame) else subset

    df_investito = safe_sum(df_totale, 'investito')
    df_valore_asset = safe_sum(df_totale, 'valore')
    df_liquidita = safe_sum(df_totale, 'liquidita')

    # Totale portafoglio (Asset + Liquidità accumulata)
    df_valore_totale = df_valore_asset + df_liquidita

    # --- CALCOLO TOP 5 DRAWDOWN ---
    rolling_max = df_valore_totale.cummax()
    with np.errstate(divide='ignore', invalid='ignore'):
        drawdown_pct = (df_valore_totale - rolling_max) / rolling_max
    drawdown_pct = drawdown_pct.fillna(0)

    # Identifichiamo i blocchi "underwater" (dove dd < 0)
    is_underwater = drawdown_pct < 0
    # Raggruppiamo i giorni consecutivi in gruppi unici
    # Trick: cumsum() incrementa ogni volta che usciamo dall'acqua, creando ID gruppo unici
    underwater_groups = drawdown_pct[is_underwater].groupby((~is_underwater).cumsum())

    dd_list = []

    for _, group in underwater_groups:
        if group.empty: continue

        # Trova il punto più basso di questo specifico periodo di crisi
        trough_date = group.idxmin()
        depth_pct = group.min()

        # Trova il picco precedente (inizio del crollo)
        # È l'ultimo giorno prima di questo gruppo in cui dd era 0
        peak_val = rolling_max.loc[trough_date]

        # Per trovare la data esatta del picco, guardiamo indietro dallo trough
        # e prendiamo l'ultimo giorno in cui il valore era uguale al rolling_max
        history_slice = df_valore_totale.loc[:trough_date]
        peak_date = history_slice[history_slice >= peak_val * 0.99999].last_valid_index()

        if peak_date:
            peak_val_real = df_valore_totale.loc[peak_date]
            trough_val = df_valore_totale.loc[trough_date]
            loss_euro = trough_val - peak_val_real

            dd_list.append({
                'pct': depth_pct * 100,  # Percentuale negativa
                'euro': loss_euro,  # Euro negativi
                'period': f"{peak_date.strftime('%d/%m/%y')} - {trough_date.strftime('%d/%m/%y')}"
            })

    # Ordina per profondità (dal più negativo al meno negativo) e prendi i primi 5
    dd_list.sort(key=lambda x: x['pct'])
    top_5_drawdowns = dd_list[:5]

    # --- DATI GRAFICO ---
    storico_grafico = []
    for data, valore in df_valore_totale.items():
        if valore > 0:
            storico_grafico.append({
                'date': data.strftime('%Y-%m-%d'),
                'valore': round(valore, 2),
                'investito': round(df_investito.loc[data], 2)
            })

    # Aggregazione Totali
    investito_tot = sum(r['investito'] for r in risultati_singoli)
    dividendi_lordi_tot = sum(r['dividendi_lordi'] for r in risultati_singoli)
    dividendi_netti_tot = sum(r['dividendi_netti'] for r in risultati_singoli)
    plusvalenza_lorda_tot = sum(r['plusvalenza_lorda'] for r in risultati_singoli)
    plusvalenza_netta_tot = sum(r['plusvalenza_netta'] for r in risultati_singoli)
    profitto_netto_tot = dividendi_netti_tot + plusvalenza_netta_tot
    valore_netto_finale = investito_tot + profitto_netto_tot
    tasse_tot = sum(r['tasse'] for r in risultati_singoli)
    roi_pct = (profitto_netto_tot / investito_tot * 100) if investito_tot > 0 else 0

    return {
        'dettagli_singoli': risultati_singoli,
        'investito': round(investito_tot, 2),
        'dividendi_lordi': round(dividendi_lordi_tot, 2),
        'dividendi_netti': round(dividendi_netti_tot, 2),
        'plusvalenza_lorda': round(plusvalenza_lorda_tot, 2),
        'plusvalenza_netta': round(plusvalenza_netta_tot, 2),
        'valore_netto': round(valore_netto_finale, 2),
        'valore_finale_lordo': round(investito_tot + plusvalenza_lorda_tot + dividendi_lordi_tot, 2),
        'profitto_pct': round(roi_pct, 2),
        'tasse': round(tasse_tot, 2),
        'top_drawdowns': top_5_drawdowns,
        'storico_grafico': storico_grafico
    }
