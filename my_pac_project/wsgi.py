"""
WSGI config for my_pac_project project.

It exposes the WSGI callable as a module-level variable named ``application``.
"""

import os
from django.core.wsgi import get_wsgi_application

# Imposta il modulo dei settings predefinito
# ASSICURATI che 'my_pac_project' corrisponda al nome della cartella che contiene settings.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'my_pac_project.settings')

# Questa è la variabile che Gunicorn sta cercando
application = get_wsgi_application()
