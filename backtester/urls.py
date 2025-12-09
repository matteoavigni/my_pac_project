from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('calcola/', views.calcolatore, name='calcolatore'),
    path('risultati/', views.risultati, name='risultati'),
    path('api/validate-ticker/', views.validate_ticker, name='validate_ticker'),
]
