"""
URL configuration for my_pac_project project.
"""
from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path('admin/', admin.site.urls),
    # include() dice a Django: "Se l'URL è vuoto (homepage), vai a vedere cosa c'è in backtester.urls"
    path('', include('backtester.urls')),
]
