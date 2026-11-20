from datetime import datetime
from unittest.mock import patch
import numpy as np
import pandas as pd
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from .services import (
    calcola_portafoglio_pac,
    compute_xirr,
    fetch_ticker_history,
    simulate_single_pac_from_df,
)


def _make_df(dates, prices, dividends=None):
    if dividends is None:
        dividends = [0.0] * len(dates)
    return pd.DataFrame(
        {'Close': prices, 'Dividends': dividends},
        index=pd.to_datetime(dates),
    )


class FinancialEngineTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_tax_rates_26_vs_12_5(self):
        dates = ['2022-01-03', '2022-06-01', '2022-12-30']
        prices = [100.0, 110.0, 120.0]
        df = _make_df(dates, prices)

        inp_26 = {
            'ticker': 'TEST26',
            'data_inizio': '2022-01-01',
            'importo_iniziale': 1000.0,
            'importo_periodico': 0.0,
            'frequenza': 1,
            'aliquota_fiscale': '26.0',
        }
        inp_125 = dict(inp_26, ticker='TEST125', aliquota_fiscale='12.5')
        opts = {'reinvest_dividends': False, 'include_bollo': False, 'commissione_ordine': 0.0}

        res_26 = simulate_single_pac_from_df(df, inp_26, options=opts)
        res_125 = simulate_single_pac_from_df(df, inp_125, options=opts)

        # +20% on 1000 => 200 gross gain
        self.assertAlmostEqual(res_26['plusvalenza_lorda'], 200.0, places=2)
        self.assertAlmostEqual(res_26['tasse_capital_gain'], 52.0, places=2)
        self.assertAlmostEqual(res_26['valore_netto'], 1148.0, places=2)

        self.assertAlmostEqual(res_125['tasse_capital_gain'], 25.0, places=2)
        self.assertAlmostEqual(res_125['valore_netto'], 1175.0, places=2)

    def test_drip_reinvestment_avoids_double_taxation(self):
        # Price flat at 100; 10 EUR dividend per share on 10 shares = 100 EUR gross div
        dates = ['2022-01-03', '2022-06-01', '2022-12-30']
        df = _make_df(dates, [100.0, 100.0, 100.0], [0.0, 10.0, 0.0])

        inp = {
            'ticker': 'DIST',
            'data_inizio': '2022-01-01',
            'importo_iniziale': 1000.0,
            'importo_periodico': 0.0,
            'frequenza': 1,
            'aliquota_fiscale': '26.0',
        }
        opts_drip = {'reinvest_dividends': True, 'include_bollo': False, 'commissione_ordine': 0.0}
        res_drip = simulate_single_pac_from_df(df, inp, options=opts_drip)

        # Gross div = 100, tax = 26, net = 74 reinvested -> 0.74 extra shares at 100 -> 1074 asset value
        # Cost basis becomes 1000 + 74 = 1074, so exit capital gain tax must be 0 (not double taxed!)
        self.assertAlmostEqual(res_drip['dividendi_lordi'], 100.0, places=2)
        self.assertAlmostEqual(res_drip['tasse_dividendi'], 26.0, places=2)
        self.assertAlmostEqual(res_drip['tasse_capital_gain'], 0.0, places=2)
        self.assertAlmostEqual(res_drip['valore_netto'], 1074.0, places=2)

        # Compare DRIP vs no-DRIP when price subsequently doubles (100 -> 100 -> 200)
        df_up = _make_df(dates, [100.0, 100.0, 200.0], [0.0, 10.0, 0.0])
        res_up_drip = simulate_single_pac_from_df(df_up, inp, options=opts_drip)
        res_up_cash = simulate_single_pac_from_df(
            df_up, inp, options={'reinvest_dividends': False, 'include_bollo': False, 'commissione_ordine': 0.0}
        )
        # With DRIP, extra 0.74 shares double in value (74 -> 148 gross, 148 - 0.26*74 = 128.76 net)
        self.assertGreater(res_up_drip['valore_netto'], res_up_cash['valore_netto'])

    def test_bollo_and_commissions(self):
        # Crosses year boundary 2022 -> 2023 with flat price 100
        dates = ['2022-01-03', '2022-12-30', '2023-01-02']
        df = _make_df(dates, [100.0, 100.0, 100.0])
        inp = {
            'ticker': 'BOLLO',
            'data_inizio': '2022-01-01',
            'importo_iniziale': 1000.0,
            'importo_periodico': 0.0,
            'frequenza': 1,
            'aliquota_fiscale': '26.0',
        }

        res_no = simulate_single_pac_from_df(
            df, inp, options={'reinvest_dividends': True, 'include_bollo': False, 'commissione_ordine': 0.0}
        )
        res_bollo = simulate_single_pac_from_df(
            df, inp, options={'reinvest_dividends': True, 'include_bollo': True, 'commissione_ordine': 5.0}
        )

        # Net buy = 995; at 2022-12-30 bollo = 0.2% of 995 = 1.99
        self.assertAlmostEqual(res_no['valore_netto'], 1000.0, places=2)
        self.assertAlmostEqual(res_bollo['commissioni'], 5.0, places=2)
        self.assertAlmostEqual(res_bollo['bollo'], 1.99, places=2)
        self.assertAlmostEqual(res_bollo['valore_netto'], 993.01, places=2)

    def test_gbp_pence_fx_conversion(self):
        class FakeTicker:
            fast_info = {'currency': 'GBp'}

            def history(self, start=None, auto_adjust=False):
                return pd.DataFrame(
                    {'Close': [2500.0, 2600.0], 'Dividends': [0.0, 100.0]},
                    index=pd.to_datetime(['2023-01-02', '2023-01-03'], utc=True),
                )

        fake_fx = pd.Series([1.15, 1.15], index=pd.to_datetime(['2023-01-02', '2023-01-03']))
        with patch('backtester.services.yf.Ticker', return_value=FakeTicker()), patch(
            'backtester.services.fetch_fx_history', return_value=fake_fx
        ):
            df, currency, err = fetch_ticker_history('FAKE.L', '2023-01-01')

        self.assertIsNone(err)
        self.assertEqual(currency, 'GBP')
        # 2500 pence = 25 GBP * 1.15 = 28.75 EUR
        self.assertAlmostEqual(float(df['Close'].iloc[0]), 28.75, places=4)
        self.assertAlmostEqual(float(df['Dividends'].iloc[1]), 1.15, places=4)

    def test_xirr_accuracy(self):
        cfs = [
            (datetime(2020, 1, 1), -1000.0),
            (datetime(2022, 1, 1), 1210.0),
        ]
        xirr = compute_xirr(cfs)
        self.assertIsNotNone(xirr)
        self.assertAlmostEqual(xirr, 10.0, delta=0.2)

    def test_negative_roi_drawdown_recovery_and_pac_vs_pic(self):
        # Build portfolio: peak 120, trough 90 (-25%), then recovers to 126, then drops to 80
        dates = pd.date_range('2021-01-04', periods=10, freq='30D')
        prices = [100.0, 110.0, 120.0, 105.0, 90.0, 110.0, 126.0, 100.0, 85.0, 80.0]
        df = _make_df(dates, prices)

        with patch('backtester.services.fetch_ticker_history', return_value=(df, 'EUR', None)):
            res = calcola_portafoglio_pac(
                [
                    {
                        'ticker': 'LOSS.MI',
                        'data_inizio': '2021-01-01',
                        'importo_iniziale': 1000.0,
                        'importo_periodico': 0.0,
                        'frequenza': 1,
                        'aliquota_fiscale': '26.0',
                    }
                ],
                options={'reinvest_dividends': True, 'include_bollo': False, 'commissione_ordine': 0.0},
            )

        self.assertNotIn('error', res)
        self.assertLess(res['profitto_pct'], 0)
        self.assertEqual(res['tasse_capital_gain'], 0.0)
        # Worst drawdown: 126 -> 80 = -36.51% (ongoing), second worst: 120 -> 90 = -25.00% (recovered)
        self.assertEqual(len(res['top_drawdowns']), 2)
        self.assertAlmostEqual(res['top_drawdowns'][0]['pct'], -36.51, places=1)
        self.assertEqual(res['top_drawdowns'][0]['recovery_label'], 'In corso')
        self.assertAlmostEqual(res['top_drawdowns'][1]['pct'], -25.0, places=1)
        self.assertNotEqual(res['top_drawdowns'][1]['recovery_label'], 'In corso')

    def test_pac_vs_pic_rising_market(self):
        dates = pd.date_range('2021-01-04', '2021-12-31', freq='B')
        prices = np.linspace(100.0, 150.0, len(dates))
        df = _make_df(dates, prices)

        with patch('backtester.services.fetch_ticker_history', return_value=(df, 'EUR', None)):
            res = calcola_portafoglio_pac(
                [
                    {
                        'ticker': 'UP.MI',
                        'data_inizio': '2021-01-04',
                        'importo_iniziale': 100.0,
                        'importo_periodico': 100.0,
                        'frequenza': 1,
                        'aliquota_fiscale': '26.0',
                    }
                ],
                options={'reinvest_dividends': True, 'include_bollo': False, 'commissione_ordine': 0.0},
            )

        self.assertGreater(res['pic']['valore_netto'], res['valore_netto'])
        self.assertLess(res['pic']['differenza_euro'], 0)
        # Last chart point matches KPI valore_netto
        self.assertAlmostEqual(res['storico_grafico'][-1]['valore'], res['valore_netto'], places=2)


class ViewAndApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()

    def test_landing_and_search_api(self):
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'MSCI World 100%')
        self.assertContains(resp, 'id="loading-overlay"', count=1)
        self.assertContains(resp, 'data-loading-trigger')

        api_resp = self.client.get(reverse('search_etf'), {'q': 'world'})
        self.assertEqual(api_resp.status_code, 200)
        tickers = [item['ticker'] for item in api_resp.json()['results']]
        self.assertIn('SWDA.MI', tickers)

    def test_preset_builder_and_validation(self):
        resp = self.client.get(reverse('calcolatore'), {'preset': 'classic_60_40'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'SWDA.MI')
        self.assertContains(resp, 'XGLE.MI')
        self.assertContains(resp, 'id="loading-overlay"', count=1)

        # Invalid submission: both initial and periodic = 0
        bad_post = self.client.post(
            reverse('calcolatore'),
            {
                'form-TOTAL_FORMS': '1',
                'form-INITIAL_FORMS': '0',
                'form-MIN_NUM_FORMS': '1',
                'form-MAX_NUM_FORMS': '1000',
                'form-0-ticker': 'SWDA.MI',
                'form-0-data_inizio': '2020-01-01',
                'form-0-importo_iniziale': '0',
                'form-0-importo_periodico': '0',
                'form-0-frequenza': '1',
                'form-0-aliquota_fiscale': '26.0',
                'commissione_ordine': '0',
            },
        )
        self.assertEqual(bad_post.status_code, 200)
        self.assertContains(bad_post, 'Inserisci almeno un importo iniziale')

    def test_full_post_to_results_negative_roi_sign_and_edit_restore(self):
        dates = pd.date_range('2022-01-03', '2022-06-30', freq='B')
        prices = np.linspace(100.0, 80.0, len(dates))
        df = _make_df(dates, prices)

        with patch('backtester.services.fetch_ticker_history', return_value=(df, 'EUR', None)):
            post_resp = self.client.post(
                reverse('calcolatore'),
                {
                    'form-TOTAL_FORMS': '1',
                    'form-INITIAL_FORMS': '0',
                    'form-MIN_NUM_FORMS': '1',
                    'form-MAX_NUM_FORMS': '1000',
                    'form-0-ticker': 'SWDA.MI',
                    'form-0-data_inizio': '2022-01-03',
                    'form-0-importo_iniziale': '1000',
                    'form-0-importo_periodico': '100',
                    'form-0-frequenza': '1',
                    'form-0-aliquota_fiscale': '26.0',
                    'reinvest_dividends': 'on',
                    'commissione_ordine': '0',
                },
                follow=True,
            )

        self.assertEqual(post_resp.status_code, 200)
        html = post_resp.content.decode('utf-8')
        # Ensure negative ROI does NOT render "+-"
        self.assertNotIn('+-', html)
        self.assertIn('Confronto PAC vs PIC', html)

        # Ensure edit=1 restores session values
        edit_resp = self.client.get(reverse('calcolatore'), {'edit': '1'})
        self.assertEqual(edit_resp.status_code, 200)
        self.assertContains(edit_resp, '2022-01-03')

    def test_results_error_redirects_back_with_message(self):
        session = self.client.session
        session['dati_pac_list'] = [
            {
                'ticker': 'BADTICKER',
                'data_inizio': '2022-01-01',
                'importo_iniziale': 1000.0,
                'importo_periodico': 0.0,
                'frequenza': 1,
                'aliquota_fiscale': '26.0',
            }
        ]
        session.save()

        with patch('backtester.services.fetch_ticker_history', return_value=(None, 'EUR', 'Ticker inesistente')):
            resp = self.client.get(reverse('risultati'), follow=True)

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Ticker inesistente')
