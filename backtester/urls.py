from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('calcola/', views.calcolatore, name='calcolatore'),
    path('demo/<slug:preset_slug>/', views.demo_preset, name='demo_preset'),
    path('risultati/', views.risultati, name='risultati'),
    path('api/validate-ticker/', views.validate_ticker, name='validate_ticker'),
    path('api/search-etf/', views.search_etf, name='search_etf'),
]
