# Deploying RevMaster

RevMaster is a Streamlit app backed by one SQLite file. No build step, no environment
variables to configure — the first user (admin) is created interactively via the in-app
setup screen on first visit.

## 1. Local / bare-metal

```bash
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

## 2. Docker

```bash
docker compose up -d --build
```

`docker-compose.yml` maps the app to `127.0.0.1:8501` and mounts `./data` for the SQLite
database, uploaded PDFs, and per-project config.

## 3. Reverse proxy (HTTPS)

Example **Caddy**:

```
yourdomain.example {
    reverse_proxy 127.0.0.1:8501
}
```

Reload after editing: `systemctl reload caddy`.

## 4. Verify

- `https://yourdomain.example/` — setup screen on first visit, login afterwards.

## 5. Updating

```bash
cd /opt/apps/revmaster
git pull
docker compose up -d --build
```

`data/` is gitignored — `git pull` never touches it.

## 6. Backups

```bash
tar czf backup-$(date +%F).tar.gz data/
```

`data/` holds the SQLite database plus every project's uploaded/fetched PDFs — copy the
whole folder, not just the `.db` file.
