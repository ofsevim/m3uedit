# Project repair plan — 2026-09-30

Scope: implement the findings accepted in the project review. Preserve local IPTV editing,
playback, exports and optional LAN sharing, while making remote deployments safe by default.

1. Regression tests: filtered saves, failed imports, metadata round trips, blocked targets,
   redirects, TLS, per-session playlists, authenticated proxy routes, safe player embedding,
   bounded downloads, main-thread progress and offline end-to-end tests.
2. Shared network policy: HTTP(S) only, validate resolved addresses and redirects, pin direct
   connections to validated IPs, verify TLS, limit downloaded bytes. Explicit private-network
   opt-in is available for trusted local installations. User-selected upstream proxies are trusted.
3. Playlist model: stable IDs, preserve hidden metadata and headers, merge visible edits;
   validate edits atomically. Build replacement lists before updating session state.
4. Proxy: unique temporary directory per session, token authorization on every route, localhost
   default, optional LAN binding, locked configuration and atomic files, bounded manifests.
5. UI: separate player, import/editor and export helpers; session resources, same-origin proxy
   routing for remote hosting, explicit HTTPS sharing, no automatic external relay fallback.
6. Delivery: mandatory offline CI tests/lint, one version/config source, working Windows/Linux
   setup, environment loading, packaging and updated operational/security documentation.

Verification: run the complete pytest suite, lint, syntax checks, build/install smoke checks,
and Streamlit AppTest flows. Browser media playback against real IPTV providers is a manual
integration check; no credentials or playlists are sent to external services during tests.

Progress: completed locally on codex/fix-project-issues; changes are uncommitted.

Verified:
- 65 tests passed on Python 3.14.0 / Streamlit 1.63.0.
- 65 tests passed on Python 3.11.9 / Streamlit 1.52.0.
- Ruff lint/format, Git whitespace and uv lock checks passed.
- Wheel 2.2.0 built and installed to a separate directory. Its launcher, CSS assets,
  empty/populated Streamlit AppTest flows and generated JavaScript syntax passed.
- Windows run.bat --check and Bash launcher syntax passed.
- Independent review findings were covered by regressions: local logo file disclosure,
  unbounded redirect drains, slow body/chunk-header deadlines and lost interchannel directives.
- Additional regressions cover missing-field playback, stop/reset and rejected file-pair updates.

Real IPTV provider playback, DRM/codec support and a Linux runtime were not exercised locally.
CI includes Windows/Linux test and package jobs.
