FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN DJANGO_SECRET_KEY=build python manage.py collectstatic --noinput
EXPOSE 8001
CMD ["sh", "-c", "python manage.py migrate && python manage.py createcachetable && gunicorn config.wsgi:application --bind 0.0.0.0:8001 --workers 2 --timeout 60"]
