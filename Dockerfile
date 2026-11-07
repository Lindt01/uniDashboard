# Basis: schlankes Debian mit Python 3.13
FROM python:3.13-slim

# Python soll keine .pyc-Dateien schreiben und Ausgaben sofort zeigen
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Arbeitsordner im Container
WORKDIR /app

# Erst nur die Paketliste kopieren und installieren.
# Solange sich requirements.txt nicht ändert, nimmt Docker diese Schicht
# aus dem Zwischenspeicher, und der Build dauert Sekunden statt Minuten.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Dann den Code
COPY pyproject.toml README.md LICENSE beispiel.xlsx ./
COPY .streamlit/ .streamlit/
COPY uni_dashboard/ uni_dashboard/
RUN pip install --no-cache-dir --no-deps .

# Nicht als root laufen
RUN useradd --create-home dashboard
USER dashboard

EXPOSE 8501

# 0.0.0.0, damit das Dashboard von außerhalb des Containers erreichbar ist
CMD ["streamlit", "run", "uni_dashboard/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]