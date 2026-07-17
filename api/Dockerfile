FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Headless Chromium til recipe-scrape-fallback (JS-renderede sider, fx nemlig).
# --with-deps installerer de nødvendige system-libs via apt.
RUN playwright install --with-deps chromium
COPY app ./app
COPY scripts ./scripts
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
