FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv:/srv/backend \
    PATH=/root/.cargo/bin:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin

WORKDIR /srv

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -LsSf https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh | sh \
    && ln -sf /root/.cargo/bin/kraken /usr/local/bin/kraken \
    && kraken --version

COPY requirements.txt /tmp/backend-requirements.txt
RUN pip install --no-cache-dir -r /tmp/backend-requirements.txt

COPY . /srv/backend
COPY --from=workspace /library /srv/backend/library
COPY --from=workspace /client.py /srv/backend/client.py
COPY --from=workspace /parser.py /srv/backend/parser.py
COPY --from=workspace /errors.py /srv/backend/errors.py
COPY --from=workspace /schema.py /srv/backend/schema.py
COPY --from=workspace /artifacts /srv/artifacts
RUN ln -s /srv/backend/app /srv/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
