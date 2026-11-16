# Direct deployment (no containers)

Runs the API and frontend as two systemd services on `172.22.226.86`. It does
not touch the existing `stockbacking-*` units, the active `backing-kronos`
service, or `/home/yanxx/backing/Finance-Llama-8B`.

## What it installs

| Path | Purpose |
| --- | --- |
| `/home/yanxx/backing/source` | Source from commit `83443f7` |
| `/opt/backing/venv` | Python 3.12 environment (conda-created under `/opt/backing/py312` if needed) with CPU torch |
| `/home/yanxx/backing/config/backend.env` | Generated runtime config, mode 600; keeps uploaded `backend.env` values when present |
| `/home/yanxx/backing/data/stock_backtest.db` | SQLite snapshot, if uploaded |
| `/home/yanxx/backing/data/backend-data` | Research cache/artifacts (symlinked as `backend/data`) |
| `backing-backend.service` | API on `127.0.0.1:8808` |
| `backing-frontend.service` | Vite preview on `0.0.0.0:5174`, proxies `/api` |

## 1. Upload

From `E:\stock` in Git Bash:

```bash
scp .deploy/backing-source-83443f7.tar.gz root@172.22.226.86:/home/yanxx/backing/backing-source.tar.gz
scp "C:/Users/13566/AppData/Local/Temp/backing-deploy/stock_backtest.snapshot.db.gz" root@172.22.226.86:/home/yanxx/backing/
scp deploy/direct/install.sh root@172.22.226.86:/home/yanxx/backing/install.sh
```

`backend/.env` is optional. If you upload it as `backend.env`, the script keeps
your AI keys and uses your existing `API_KEY`. Without it, the script generates
`API_KEY` and `SESSION_SECRET`, reads `KRONOS_SERVICE_TOKEN` from
`/home/yanxx/kronos-service/service.env`, and you can set the DeepSeek key later
in the web UI.

Skip the database snapshot if you want to start empty; the script runs Alembic
and creates the schema on the server.

## 2. Run

```bash
ssh root@172.22.226.86
cd /home/yanxx/backing
bash install.sh
```

The script creates a Python 3.12 environment, installs CPU torch and the backend
dependencies, restores the snapshot, runs migrations, builds the frontend, and
starts both services. It ends with a health check.

## 3. Access

- Site: `http://172.22.226.86:5174`
- Login: `admin`; the password is `API_KEY` in
  `/home/yanxx/backing/config/backend.env` unless `AUTH_PASSWORD` is set there.
- AI keys: open the web UI's AI settings, or edit `config/backend.env` and
  restart `backing-backend`.

## Management

```bash
systemctl status backing-backend backing-frontend
journalctl -u backing-backend -u backing-frontend -n 100 --no-pager
systemctl restart backing-backend backing-frontend
```

After changing the runtime config, edit
`/home/yanxx/backing/config/backend.env` and restart `backing-backend`.

After changing source, upload a new archive and rerun `install.sh`. The existing
database is kept; set `REPLACE_DB=1` to replace it with the uploaded snapshot.

## Notes

- HTTP only: `APP_ENV=development` and `SESSION_HTTPS_ONLY=false`. The API binds
  `127.0.0.1`; only the frontend port is exposed. For HTTPS, put a TLS reverse
  proxy in front and switch to `APP_ENV=production` plus
  `SESSION_HTTPS_ONLY=true`.
- Port `5174/tcp` is already open in firewalld; the script adds it if missing.
- The frontend runs `vite preview`, which inherits the `/api` and WebSocket proxy
  from `vite.config.ts`.
- Python 3.12 is created under `/opt/backing/py312` when the host does not
  provide it. Dependencies install into `/opt/backing/venv`; the installer runs
  `restorecon` there so systemd can execute the interpreter under SELinux.
- The server cannot reach the configured mootdx quote servers, so the generated
  config uses `tencent` HTTPS for quotes and K-lines.
- `KRONOS_SERVICE_URL` is set to `http://172.22.226.86:8211`; keep the existing
  `backing-kronos.service` active for DL predictions.
- Both services run as the unprivileged `yanxx` user; the installer uses root
  only to create systemd units and set ownership. It uses the system Node at
  `/usr/bin/npm`.
