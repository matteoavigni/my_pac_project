import os
from pathlib import Path
import dj_database_url # Importante per il DB su Render

BASE_DIR = Path(__file__).resolve().parent.parent

# --- SICUREZZA ---
# Prendi la chiave segreta dalle variabili d'ambiente, altrimenti usa una default insicura (solo per dev)
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-chiave-di-sviluppo-locale')

# DEBUG deve essere False in produzione!
# Render imposterà la variabile RENDER a 'true'
DEBUG = 'RENDER' not in os.environ

# Permetti l'host di Render
ALLOWED_HOSTS = []
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# --- DATABASE ---
# Usa dj_database_url per connettersi a Postgres su Render, altrimenti SQLite locale
DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///' + str(BASE_DIR / 'db.sqlite3'),
        conn_max_age=600
    )
}

# --- STATIC FILES (WhiteNoise) ---
# WhiteNoise serve per servire CSS/JS senza un server Nginx separato
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # <--- AGGIUNGI QUESTO SUBITO DOPO SECURITY
    'django.contrib.sessions.middleware.SessionMiddleware',
    # ... altri middleware ...
]

STATIC_URL = 'static/'
# Dove Django raccoglierà i file statici
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
# Compressione e caching per performance
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
