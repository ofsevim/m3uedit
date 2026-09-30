# M3U Editor Pro

A Streamlit app for loading, editing, checking and exporting IPTV playlists.
[Türkçe](README.tr.md) · [Quick start](QUICKSTART.md) · [Deployment](docs/DEPLOYMENT.md)

## Start

Python 3.11+ is required. Clone https://github.com/ofsevim/m3uedit and run:

- Windows: `run.bat`
- Linux/macOS: `bash run.sh`

The launcher creates `.venv` when necessary, reuses an existing `.venv` or `venv`,
installs missing dependencies and opens the app on http://127.0.0.1:8501.
Run `python bootstrap.py --check` to check setup without starting the server.

Manual setup: `python -m pip install -e .`, then `m3uedit`.
`streamlit run app.py` and the compatibility entrypoint `streamlit run src/app.py` also work.
Copy `.env.example` to `.env` for optional settings; existing process environment values take precedence.
The launcher applies SERVER_HOST, SERVER_PORT and MAX_FILE_SIZE_MB to Streamlit.

## Workflows

- Load a public HTTP(S) URL or upload an M3U/M3U8 file.
- Filter by group, type, status or name. Saving a filtered table retains hidden channels and metadata.
- Add or delete channels. Invalid edits and failed loads retain the existing playlist.
- Run health checks; results are probes, not guarantees that playback will succeed.
- Prepare M3U, M3U8, CSV, JSON, TXT or a proxy playlist on demand.
- Explicitly publish an authenticated local playlist link or send a snapshot to a selected HTTPS paste service.

M3U headers, EPG attributes, unknown EXTINF attributes, comma-containing names and channel directives
are retained on M3U export. CSV/JSON contain the visible channel fields.

## Network defaults

TLS certificates are verified. Non-HTTP(S), private, loopback and link-local targets are blocked,
including redirect destinations. Direct connections use validated DNS addresses.
The proxy binds to localhost on port 8502 and requires an unguessable per-session token.
Each session has its own settings and temporary files; resources expire with the session/process.
LAN sharing and private-source access are separate opt-ins. Only trusted local installations should enable them.
An explicitly selected upstream HTTP(S) proxy is trusted to resolve and connect to provider hosts.
SOCKS URLs are not supported; use the HTTP port exposed by your VPN client.

Remote browser playback requires a reachable HTTPS reverse proxy configured through
PROXY_PUBLIC_BASE_URL and PROXY_ALLOWED_ORIGIN; localhost addresses in a remote browser refer to that browser's computer.
See [deployment](docs/DEPLOYMENT.md). No automatic external stream relay is used.
DRM-protected sources are not supported; HLS and MPEG-TS have the primary playback path.

## Development

```sh
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check app.py bootstrap.py setup.py src utils ui static tests
```

The tests use local fixtures and block external connections. CI requires tests and lint to pass
on Windows/Linux with Python 3.11/3.14, then builds the wheel. Version metadata comes from `utils.__version__`.

MIT license. See [architecture](docs/ARCHITECTURE.md), [API](docs/API.md) and [security](SECURITY.md).
