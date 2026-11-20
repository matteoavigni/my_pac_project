import json
from django.contrib import messages
from django.forms import formset_factory
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .etf_catalog import PORTFOLIO_PRESETS, search_catalog
from .forms import PACForm, SimulationOptionsForm
from .services import calcola_portafoglio_pac, get_ticker_metadata

DEFAULT_ETF_INITIAL = [
    {
        'ticker': 'SWDA.MI',
        'data_inizio': '2018-01-01',
        'importo_iniziale': 1000,
        'importo_periodico': 200,
        'frequenza': 1,
        'aliquota_fiscale': '26.0',
    }
]

DEFAULT_OPTIONS = {
    'reinvest_dividends': True,
    'include_bollo': True,
    'commissione_ordine': 0.0,
}


def home(request):
    return render(
        request,
        'backtester/landing.html',
        {'presets': list(PORTFOLIO_PRESETS.values())},
    )


def demo_preset(request, preset_slug):
    preset = PORTFOLIO_PRESETS.get(preset_slug)
    if not preset:
        return redirect('calcolatore')

    request.session['dati_pac_list'] = preset['etfs']
    request.session['pac_options'] = preset['options']
    return redirect('risultati')


def validate_ticker(request):
    """API endpoint per validare un ticker e recuperare nome, valuta e data iniziale."""
    ticker = request.GET.get('ticker', '')
    meta = get_ticker_metadata(ticker)
    return JsonResponse(meta)


def search_etf(request):
    """API endpoint per l'autocomplete dal catalogo ETF curato."""
    query = request.GET.get('q', '')
    results = search_catalog(query, limit=8)
    return JsonResponse({'results': results})


def calcolatore(request):
    PACFormSet = formset_factory(PACForm, extra=0, min_num=1, validate_min=True)
    active_preset = None

    if request.method == 'POST':
        formset = PACFormSet(request.POST)
        options_form = SimulationOptionsForm(request.POST)
        if formset.is_valid() and options_form.is_valid():
            dati_input_list = []
            for form in formset:
                if form.cleaned_data and form.cleaned_data.get('ticker'):
                    dati = dict(form.cleaned_data)
                    dati['data_inizio'] = dati['data_inizio'].strftime('%Y-%m-%d')
                    dati['frequenza'] = int(dati['frequenza'])
                    dati_input_list.append(dati)

            if dati_input_list:
                request.session['dati_pac_list'] = dati_input_list
                request.session['pac_options'] = {
                    'reinvest_dividends': bool(options_form.cleaned_data.get('reinvest_dividends')),
                    'include_bollo': bool(options_form.cleaned_data.get('include_bollo')),
                    'commissione_ordine': float(options_form.cleaned_data.get('commissione_ordine') or 0.0),
                }
                return redirect('risultati')
    else:
        preset_slug = request.GET.get('preset')
        edit_mode = request.GET.get('edit')

        if preset_slug and preset_slug in PORTFOLIO_PRESETS:
            active_preset = preset_slug
            initial_etfs = PORTFOLIO_PRESETS[preset_slug]['etfs']
            initial_opts = PORTFOLIO_PRESETS[preset_slug]['options']
        elif edit_mode and request.session.get('dati_pac_list'):
            initial_etfs = request.session['dati_pac_list']
            initial_opts = request.session.get('pac_options', DEFAULT_OPTIONS)
        else:
            initial_etfs = DEFAULT_ETF_INITIAL
            initial_opts = DEFAULT_OPTIONS

        formset = PACFormSet(initial=initial_etfs)
        options_form = SimulationOptionsForm(initial=initial_opts)

    return render(
        request,
        'backtester/input.html',
        {
            'formset': formset,
            'options_form': options_form,
            'presets': list(PORTFOLIO_PRESETS.values()),
            'active_preset': active_preset,
        },
    )


def risultati(request):
    dati_list = request.session.get('dati_pac_list')
    if not dati_list:
        return redirect('calcolatore')

    options = request.session.get('pac_options', DEFAULT_OPTIONS)
    risultato = calcola_portafoglio_pac(dati_list, options=options)

    if not risultato or 'error' in risultato:
        err_msg = (risultato or {}).get('error', 'Impossibile completare la simulazione.')
        messages.error(request, err_msg)
        return redirect(f"{reverse('calcolatore')}?edit=1")

    for warn in risultato.get('warnings', []):
        messages.warning(request, warn)

    context = {
        'risultato': risultato,
        'dati_input_list': dati_list,
        'grafico_json': json.dumps(risultato['storico_grafico']),
        'allocazione_json': json.dumps(risultato['allocazione']),
    }
    return render(request, 'backtester/results.html', context)
