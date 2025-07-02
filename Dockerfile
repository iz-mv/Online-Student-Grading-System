FROM python:3.11

WORKDIR /app

COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

ENV FLASK_APP=run.py
ENV FLASK_ENV=development

EXPOSE 5050

CMD ["flask", "run", "--host=0.0.0.0", "--port=5050"]

