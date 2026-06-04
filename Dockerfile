FROM python:3.10-alpine

WORKDIR /app

# Install only runtime dependencies
RUN apk add --no-cache --virtual .build-deps gcc musl-dev && \
    pip install --no-cache-dir --compile \
    fastapi==0.110.0 \
    uvicorn==0.28.0 \
    jinja2==3.1.3 \
    python-multipart==0.0.9 \
    python-dotenv==1.0.0 \
    qrcode[pil]==7.4.2 && \
    apk del .build-deps

COPY main.py .
COPY templates/ ./templates/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
