FROM python:3-slim AS builder
ADD *.py /app/
WORKDIR /app

RUN pip install --target=/app requests
RUN pip install --target=/app -U pip setuptools wheel
RUN pip install --target=/app ruamel.yaml

FROM ubuntu AS ubuntu-runtime
RUN apt update -y && apt install -y python3 git
COPY --from=builder /app /app
WORKDIR /app
ENV PYTHONPATH /app
CMD ["python3", "/app/main.py"]

FROM gcr.io/distroless/python3-debian12
COPY --from=builder /app /app
WORKDIR /app
ENV PYTHONPATH /app
CMD ["/app/main.py"]