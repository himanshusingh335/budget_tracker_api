FROM python:3.13-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir flask

ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=8502
ENV FLASK_ENV=production

EXPOSE 8502

CMD ["flask", "run"]
#docker run -d -p 8502:8502 -v budget_data:/app/data --name budget_tracker_api mariox1105/budget-tracker-api