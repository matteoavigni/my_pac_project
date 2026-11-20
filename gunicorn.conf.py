import os

port = os.environ.get("PORT") or "10000"
bind = f"0.0.0.0:{port}"
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
accesslog = "-"
errorlog = "-"
loglevel = "info"
control_socket_disable = True
