from django import forms


class PACForm(forms.Form):
    ticker = forms.CharField(
        label='Ticker ETF',
        max_length=20,
        initial='SWDA.MI',
        help_text='Es. SWDA.MI, CSSPX.MI, VNGA80.MI',
        widget=forms.TextInput(attrs={
            'class': 'ticker-input',  # <--- Classe per il Javascript
            'autocomplete': 'off',
            'placeholder': 'Cerca Ticker...'
        })
    )
    data_inizio = forms.DateField(
        label='Data Inizio',
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial='2019-01-01'
    )
    importo_iniziale = forms.FloatField(
        label='Investimento Iniziale (€)',
        min_value=0,
        initial=0
    )
    importo_periodico = forms.FloatField(
        label='Rata Periodica (€)',
        min_value=10,
        initial=100
    )
    frequenza = forms.ChoiceField(
        choices=[
            (1, 'Mensile'),
            (3, 'Trimestrale'),
            (6, 'Semestrale'),
            (12, 'Annuale')
        ],
        initial=1
    )
