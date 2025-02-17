FROM python:3.10.6

WORKDIR /app

COPY requirements.txt .

RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY . .

CMD gunicorn app:app & python3 src/bot.py
