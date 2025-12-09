# my_pac_project
A Django-based backtesting tool for ETF Accumulation Plans (PAC). Features historical performance analysis, drawdown calculation, and Italian tax optimization using real-time market data.


## Local deploy

Create the Django DB:

```bash
python manage.py migrate
```

Run the command below to run a local instance of the server:

```bash
python manage.py runserver
```