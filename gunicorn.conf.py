wsgi_app = "config.wsgi"
bind = "unix:/srv/http/staging.bakeup.org/run/gunicorn.socket"
workers = 3
