FROM python:3.11-alpine3.17

LABEL org.opencontainers.image.description="Deltadore Tydom to MQTT Bridge"

# App base dir
WORKDIR /app

# Copy app
COPY /app .

# Install dependencies
RUN pip3 install -r requirements.txt

# Expose health check port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python /app/healthcheck.py

# Main command
CMD [ "python", "-u", "main.py" ]
