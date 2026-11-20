# 📈 PAC Simulator (ETF Backtester & Fiscalità Italiana)

Applicazione web Django per il backtest multi-ETF di Piani di Accumulo Capitale (**PAC**) su dati storici reali, progettata per investitori e consulenti finanziari italiani.

## ✨ Funzionalità Principali

* **Catalogo ETF & Autocomplete:** Ricerca rapida integrata per ticker, nome o categoria (es. `SWDA.MI`, `VWCE.MI`, `XGLE.MI`, `VOO`) con validazione automatica su Yahoo Finance per qualsiasi altro ticker.
* **Portafogli Pronti (1-Click Demo):** Preset preconfigurati (*MSCI World 100%*, *Bilanciato 60/40 White List*, *Globale + Emergenti 80/20*, *S&P 500 + Nasdaq USD→EUR*) avviabili con un click o personalizzabili.
* **Multi-Valuta & Conversione Storica:** Converte automaticamente ETF in USD o GBP (inclusi titoli quotati in pence `GBp`/`GBX`) in Euro usando la serie storica giornaliera dei tassi di cambio.
* **Fiscalità Italiana Completa:**
  * Aliquota configurabile per singolo ETF: **26%** (standard/azionario) o **12,5%** (titoli di Stato White List).
  * Opzione **DRIP** (reinvestimento dividendi netti) senza doppia tassazione sul capital gain finale.
  * Calcolo opzionale dell'**imposta di bollo (0,20%/anno)** a fine anno solare e **commissioni per eseguito**.
* **Metriche Quantitative & Confronto PAC vs PIC:**
  * **XIRR Netto Annualizzato**, **Volatilità Annualizzata (TWRR)**, confronto diretto **Lordo vs Netto** e **PAC vs PIC (Lump Sum)**.
  * **Analisi Drawdown:** grafico *underwater* interattivo e tabella Top 5 Drawdown con durata e tempi di recupero.
  * **Riepilogo Anno per Anno** e ripartizione allocazione finale.
* **Reportistica:** Export diretto della serie storica in **CSV** e stampa/salvataggio in **PDF** con layout dedicato.

## 🛠️ Tech Stack

* **Backend:** Python 3.12, Django 5
* **Motore Quantitativo:** Pandas, NumPy, yfinance, ThreadPoolExecutor + Django Cache (`LocMemCache`)
* **Frontend:** HTML5, CSS3 (Light/Dark Mode & Print CSS), Vanilla JavaScript, Chart.js
* **Deployment:** Render.com (Gunicorn + WhiteNoise)

## 🚀 Avvio Locale

```bash
git clone git@github.com:matteoavigni/my_pac_project.git
cd my_pac_project

uv venv --python python3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt

python manage.py migrate
python manage.py runserver
```

Apri `http://127.0.0.1:8000` nel browser.

## 🧪 Test

```bash
python manage.py test backtester
```

## ⚠️ Disclaimer

Strumento a scopo esclusivamente educativo e informativo. I rendimenti storici non sono indicativi dei risultati futuri e non costituiscono consulenza finanziaria personalizzata.

**Developed by [Matteo Avigni](https://matteoavigni.github.io/)**
