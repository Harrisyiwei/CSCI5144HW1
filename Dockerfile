FROM python:3.12-alpine

WORKDIR /app

COPY server.py .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "server.py", "--port", "8000"]