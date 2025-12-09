import json

import yfinance as yf
from django.forms import formset_factory
from django.http import JsonResponse
from django.shortcuts import render, redirect

from .forms import PACForm
from .services import calcola_portafoglio_pac


def home(request):
    return render(request, 'backtester/landing.html')


def validate_ticker(request):
    """API endpoint per controllare se un ticker esiste"""
    ticker = request.GET.get('ticker', '').upper().strip()

    if not ticker:
        return JsonResponse({'valid': False, 'error': 'Inserisci un ticker'})

    try:
        # Usiamo yfinance per scaricare solo i metadati (veloce)
        ticker_obj = yf.Ticker(ticker)

        # Proviamo a recuperare il nome.
        # Nota: .info a volte può essere lento o fallire su Render free tier se l'IP è flaggato,
        # ma è il metodo standard.
        info = ticker_obj.info

        # Yahoo a volte restituisce un dizionario vuoto o con errori se non trova nulla
        # ma non solleva eccezione. Controlliamo se ha un nome.
        long_name = info.get('longName') or info.get('shortName')

        if long_name:
            return JsonResponse({'valid': True, 'name': long_name})
        else:
            return JsonResponse({'valid': False, 'error': 'Ticker non trovato o dati non disponibili'})

    except Exception as e:
        return JsonResponse({'valid': False, 'error': 'Ticker non valido'})


def calcolatore(request):
    # Creiamo un Formset: una fabbrica che genera N form di tipo PACForm
    # extra=1 significa che mostra 1 form vuoto di default
    PACFormSet = formset_factory(PACForm, extra=1)

    if request.method == 'POST':
        formset = PACFormSet(request.POST)
        if formset.is_valid():
            dati_input_list = []
            for form in formset:
                # Il formset potrebbe contenere form vuoti se l'utente li ha lasciati tali
                if form.cleaned_data and form.cleaned_data.get('ticker'):
                    dati = form.cleaned_data
                    dati['data_inizio'] = dati['data_inizio'].strftime('%Y-%m-%d')
                    dati_input_list.append(dati)

            if dati_input_list:
                request.session['dati_pac_list'] = dati_input_list
                return redirect('risultati')
    else:
        # Pre-popoliamo con un esempio se vuoto
        formset = PACFormSet()

    return render(request, 'backtester/input.html', {'formset': formset})


def risultati(request):
    dati_list = request.session.get('dati_pac_list')
    if not dati_list:
        return redirect('calcolatore')

    risultato = calcola_portafoglio_pac(dati_list)

    if not risultato:
        # Gestione caso errore download (es. ticker sbagliato)
        # In un'app reale mostreremmo un messaggio di errore
        return redirect('calcolatore')

    context = {
        'risultato': risultato,
        'grafico_json': json.dumps(risultato['storico_grafico'])
    }
    return render(request, 'backtester/results.html', context)
