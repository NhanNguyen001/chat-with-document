# Gunicorn configuration file
import multiprocessing

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 300
keepalive = 2

# Process naming
proc_name = "chatdoc"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Restart workers when code changes
reload = True

# Maximum requests a worker will process before restarting
max_requests = 1000
max_requests_jitter = 50

# Process management
preload_app = True
