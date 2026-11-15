FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home widen
COPY --chown=widen:widen server.py /app/server.py
COPY --chown=widen:widen souk_service.py /app/souk_service.py
COPY --chown=widen:widen public/ /app/public/
USER widen
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh","-c","exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
