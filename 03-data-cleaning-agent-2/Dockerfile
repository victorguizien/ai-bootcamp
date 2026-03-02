FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8502
EXPOSE ${PORT}

CMD streamlit run app.py --server.address 0.0.0.0 --server.port ${PORT}
