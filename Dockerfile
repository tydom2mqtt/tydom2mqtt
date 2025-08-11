FROM python:3.11-alpine3.22

LABEL org.opencontainers.image.description="Deltadore Tydom to MQTT Bridge"

# App base dir
WORKDIR /app

# Copy app
COPY /app .

# Install dependencies
RUN pip3 install -r requirements.txt

# Main command
CMD [ "python", "-u", "main.py" ]
