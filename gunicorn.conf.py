import os

import yaml

bind = "0.0.0.0:8080"
workers = os.getenv("GUNICORN_WORKERS", 4)
accesslog = "/tmp/recommendation.access.log"
wsgi_app = "recommendation.main:app"
worker_class = "uvicorn.workers.UvicornWorker"

with open("logging.yaml", "rt") as f:
    log_config = yaml.safe_load(f.read())
logconfig_dict = log_config

# The maximum number of requests a worker will process before restarting.
# This is a simple method to help limit the damage of memory leaks.if any
max_requests = 1000
# The maximum jitter to add to the max_requests setting.
# This is intended to stagger worker restarts to avoid all workers restarting at the same time.
max_requests_jitter = 50
