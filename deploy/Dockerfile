FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev libldap2-dev libsasl2-dev libxml2-dev libxslt1-dev libjpeg-dev && rm -rf /var/lib/apt/lists/*
COPY odoo-c/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
CMD ["python", "/opt/odoo-c/odoo-bin", "-c", "/etc/odoo.conf"]
