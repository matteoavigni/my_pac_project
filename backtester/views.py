from django.shortcuts import render, redirect
from django.forms import formset_factory
from django.http import JsonResponse
from .forms import PACForm
from .services import calcola_portafoglio_pac
import json
import yfinance as yf


def home(request):
    return render(request, 'backtester/landing.html')


def validate_ticker(request):
    """API endpoint per controllare se un ticker esiste e recuperare la data di inizio."""
    ticker = request.GET.get('ticker', '').upper().strip()

    if not ticker:
        return JsonResponse({'valid': False, 'error': 'Inserisci un ticker'})

    try:
        ticker_obj = yf.Ticker(ticker)

        # 1. Recuperiamo le info di base (Nome)
        # Nota: l'accesso a .info forza una chiamata API
        info = ticker_obj.info
        long_name = info.get('longName') or info.get('shortName') or ticker

        # 2. Recuperiamo la prima data di trading disponibile
        # Scarichiamo tutto lo storico (solo metadata se possibile sarebbe meglio, ma history è più affidabile)
        # Usiamo 'max' per trovare l'inizio assoluto.
        hist = ticker_obj.history(period="max", auto_adjust=False)

        if hist.empty:
            return JsonResponse({'valid': False, 'error': 'Dati non disponibili per questo ticker'})

        # Prendiamo la prima data dell'indice e la formattiamo YYYY-MM-DD
        first_date = hist.index[0].date().isoformat()

        return JsonResponse({
            'valid': True,
            'name': long_name,
            'first_date': first_date  # <--- Inviamo la data minima al frontend
        })

    except Exception as e:
        print(f"Errore validazione {ticker}: {e}")
        return JsonResponse({'valid': False, 'error': 'Ticker non valido o errore API'})


def calcolatore(request):
    PACFormSet = formset_factory(PACForm, extra=1)

    if request.method == 'POST':
        formset = PACFormSet(request.POST)
        if formset.is_valid():
            dati_input_list = []
            for form in formset:
                if form.cleaned_data and form.cleaned_data.get('ticker'):
                    dati = form.cleaned_data
                    dati['data_inizio'] = dati['data_inizio'].strftime('%Y-%m-%d')
                    dati_input_list.append(dati)

            if dati_input_list:
                request.session['dati_pac_list'] = dati_input_list
                return redirect('risultati')
    else:
        formset = PACFormSet()

    return render(request, 'backtester/input.html', {'formset': formset})


def risultati(request):
    dati_list = request.session.get('dati_pac_list')
    if not dati_list:
        return redirect('calcolatore')

    risultato = calcola_portafoglio_pac(dati_list)

    if not risultato:
        return redirect('calcolatore')

    context = {
        'risultato': risultato,
        'grafico_json': json.dumps(risultato['storico_grafico'])
    }
    return render(request, 'backtester/results.html', context)
