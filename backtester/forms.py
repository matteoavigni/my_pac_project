from django import forms


class PACForm(forms.Form):
    ticker = forms.CharField(
        label='Ticker ETF',
        max_length=20,
        initial='SWDA.MI',
        help_text='Es. SWDA.MI, VWCE.MI, CSSPX.MI',
        widget=forms.TextInput(attrs={
            'class': 'ticker-input',
            'autocomplete': 'off',
            'placeholder': 'Es. SWDA.MI o cerca ETF per nome...'
        })
    )
    data_inizio = forms.DateField(
        label='Data Inizio',
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial='2018-01-01'
    )
    importo_iniziale = forms.FloatField(
        label='Investimento Iniziale (€)',
        min_value=0,
        initial=1000,
        widget=forms.NumberInput(attrs={'step': '50', 'min': '0'})
    )
    importo_periodico = forms.FloatField(
        label='Rata Periodica (€)',
        min_value=0,
        initial=200,
        widget=forms.NumberInput(attrs={'step': '10', 'min': '0'})
    )
    frequenza = forms.ChoiceField(
        label='Frequenza',
        choices=[
            (1, 'Mensile'),
            (3, 'Trimestrale'),
            (6, 'Semestrale'),
            (12, 'Annuale'),
        ],
        initial=1
    )
    aliquota_fiscale = forms.ChoiceField(
        label='Aliquota Fiscale',
        choices=[
            ('26.0', '26% (Standard / Azionario)'),
            ('12.5', '12,5% (Titoli di Stato White List)'),
        ],
        initial='26.0'
    )

    def clean_ticker(self):
        return (self.cleaned_data.get('ticker') or '').upper().strip()

    def clean(self):
        cleaned = super().clean()
        iniziale = cleaned.get('importo_iniziale')
        periodico = cleaned.get('importo_periodico')
        if iniziale is not None and periodico is not None:
            if iniziale <= 0 and periodico <= 0:
                raise forms.ValidationError(
                    "Inserisci almeno un importo iniziale o una rata periodica maggiore di 0 €."
                )
        return cleaned


class SimulationOptionsForm(forms.Form):
    reinvest_dividends = forms.BooleanField(
        required=False,
        initial=True,
        label='Reinvesti dividendi netti (DRIP)'
    )
    include_bollo = forms.BooleanField(
        required=False,
        initial=True,
        label='Includi imposta di bollo (0,20%/anno)'
    )
    commissione_ordine = forms.FloatField(
        required=False,
        min_value=0,
        max_value=100,
        initial=0.0,
        label='Commissione per acquisto (€)',
        widget=forms.NumberInput(attrs={'step': '0.5', 'min': '0', 'max': '100'})
    )

    def clean_commissione_ordine(self):
        val = self.cleaned_data.get('commissione_ordine')
        return float(val) if val is not None else 0.0
