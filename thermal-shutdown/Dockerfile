FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py hosts.yml ./
RUN mkdir -p /app/keys
EXPOSE 9095
CMD ["python", "app.py"]
