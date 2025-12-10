# 📈 PAC Simulator (ETF Backtester)

A comprehensive web application built with Django to backtest Dollar Cost Averaging (PAC - *Piano di Accumulo Capitale*) strategies on ETFs using real historical market data.

Designed specifically for Italian investors, it handles currency conversion (USD/EUR) and calculates the **Italian Capital Gain Tax (26%)** automatically.

## ✨ Key Features

* **Multi-ETF Support:** Construct a portfolio with multiple ETFs weighted differently.
* **Real-Time Data:** Fetches historical data (prices, dividends, splits) directly from Yahoo Finance via `yfinance`.
* **Smart Currency Handling:** Automatically converts non-EUR assets (e.g., SPY, QQQ) to Euros using historical exchange rates for precise valuation.
* **Italian Taxation Logic:**
  * Separates **Capital Gains** (quote appreciation) from **Dividends** (cash flow).
  * Applies the 26% tax rate on realized gains and collected coupons.
  * Calculates "Net Portfolio Value" vs "Gross Value".
* **Risk Analysis:**
  * Calculates **Max Drawdown** (percentage, monetary loss, and duration).
  * dentifies and tabulates the top 5 worst performance periods in the portfolio's history.
* **Interactive Visualizations:** Responsive charts using **Chart.js** to visualize portfolio growth vs. invested capital.


## 🛠️ Tech Stack

* **Backend:** Python 3.11, Django 5
* **Data Analysis:** Pandas, NumPy, yfinance
* **Frontend:** HTML5, CSS3, JavaScript (Chart.js for dataviz)
* **Deployment:** Render.com (Gunicorn + WhiteNoise)


## 🚀 Local Installation

Follow these steps to run the project locally on your machine.

**Prerequisites**

* Python 3.8 or higher
* pip (Python package manager)

**Installation**

1. **Clone the repository:**

    ```bash
    git clone git@github.com:matteoavigni/my_pac_project.git
    cd my_pac_project
    ```
2. **Create and activate a virtual environment:**

    ```bash
    # macOS/Linux
    python3 -m venv .venv
    source .venv/bin/activate
    
    # Windows
    python -m venv .venv
    .venv\Scripts\activate
    ```

3. **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```
   
4. **Apply database migrations:** (Required for session management, even if no custom models are used)

    ```bash
    python manage.py migrate
    ```
   
5. **Run the development server:**

    ```bash
    python manage.py runserver
    ```

6. **Access the app:** Open your browser and go to `http://127.0.0.1:8000`


## 🌍 Deployment

The project is configured for deployment on Render.com. It includes a `build.sh` script and production settings using `dj-database-url` and `whitenoise` for static files.

## ⚠️ Disclaimer

This tool is for educational and informational purposes only. Past performance is not indicative of future results. It does not constitute financial advice.





**Developed by [Matteo Avigni](https://matteoavigni.github.io/)**
