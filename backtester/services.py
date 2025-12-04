# backtester/services.py
import yfinance as yf
import pandas as pd


def calcola_performance_pac(ticker, importo, data_inizio, frequenza):
    """
    Logica business pura.
    Non usa request/response, restituisce solo dati (dizionari o oggetti).
    """
    try:
        # Esempio download dati
        df = yf.download(ticker, start=data_inizio, progress=False)
        if df.empty:
            return None

        # ... qui inserisci la tua logica matematica del PAC ...
        # (Codice che abbiamo discusso in precedenza)

        return {
            "valore_finale": 10000,
            "investito": 8000,
            "grafico": [...]
        }
    except Exception as e:
        print(f"Errore API: {e}")
        return None
