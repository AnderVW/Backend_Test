FROM python:3.11-bullseye

# Install system dependencies for compiling Python packages (postgres)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3-dev \
    libpq-dev \
    gcc \
    wget && \
    pip install --upgrade pip wheel setuptools

COPY /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get purge -y --auto-remove \
    python3-dev \
    gcc \
    wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY /app /app
WORKDIR /app

# Create a startup script with proper error handling
RUN echo '#!/bin/bash\n\
set -e\n\
cd /app\n\
\n\
echo "Starting Gunicorn WSGI server..."\n\
exec gunicorn --workers=4 --threads=4 --timeout=60 --max-requests=500 --max-requests-jitter=50 --bind=0.0.0.0:8081 core.wsgi:application\n\
\n\
' > /start.sh && chmod +x /start.sh

ENV MODULE_NAME="core.wsgi"
ENV VARIABLE_NAME="application"
# Expose port
EXPOSE 8081

# Run the startup script
CMD ["/start.sh"]


