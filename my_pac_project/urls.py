"""
URL configuration for my_pac_project project.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

# Una semplice view per verificare che la homepage funzioni subito
def home(request):
    return HttpResponse("<h1>Il Backtester PAC è online! 🚀</h1><p>Ora puoi iniziare a sviluppare la tua app.</p>")

urlpatterns = [
    path('admin/', admin.site.urls),
    # path('', include('backtester.urls')), # Scommenta questa riga quando avrai creato backtester/urls.py
    path('', home), # Rimuovi questa riga quando attivi quella sopra
]
