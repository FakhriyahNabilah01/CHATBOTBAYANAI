FROM python:3.11-slim

WORKDIR /app

# install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy source code
COPY . .

# Railway/Heroku style: listen on $PORT
ENV PYTHONUNBUFFERED=1

# jalankan FastAPI app yang ada di src/waha_api.py
CMD ["sh", "-c", "uvicorn waha_api:app --host 0.0.0.0 --port ${PORT:-8000} --app-dir src"]
