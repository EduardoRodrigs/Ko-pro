import os
import multiprocessing

# Port binding
bind = f"0.0.0.0:{os.getenv('PORT', '10000')}"

# Safe worker configuration for containerized environments
try:
    cores = multiprocessing.cpu_count()
    default_workers = max(2, min(cores * 2, 4))
except Exception:
    default_workers = 2

workers = int(os.getenv("WEB_CONCURRENCY", default_workers))
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
