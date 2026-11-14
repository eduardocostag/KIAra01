# Kiara SDR worker (Debian)

Installed at `/opt/kiara/sdr`. A systemd timer calls `POST /v1/sdr/internal/tick` on the Kiara API every
75-135 s (randomized). The API does the work: sync WhatsApp (OpenWA), understand conversations, update the
funnel, draft or send replies and follow-ups, and hand over to a person. Sending always goes through the
anti-ban rules (only contacts who already wrote, human spacing and typing, no blasts, contact hours).

`/opt/kiara/sdr/.env` (root, 0600), read through systemd `LoadCredential`:

    KIARA_API_URL=https://kiara-api-rouge.vercel.app
    KIARA_WORKER_TOKEN=<same value as KIARA_WORKER_TOKEN on the Vercel API>

Install: copy `kiara-sdr-tick.sh` (0755) to `/usr/local/lib/kiara/` (/opt/kiara is root-only; the service runs as a dynamic user), the unit and timer to `/etc/systemd/system/`,
then `systemctl daemon-reload && systemctl enable --now kiara-sdr.timer`. Logs: `journalctl -u kiara-sdr`.
