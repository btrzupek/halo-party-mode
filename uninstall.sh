#!/usr/bin/env bash
# Remove halo-party-mode. Stopping the service restores the original LED color.
# Run on the Halo itself:  sudo ./uninstall.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Please run as root: sudo $0" >&2
    exit 1
fi

systemctl disable --now halo-led-temp.service 2>/dev/null || true
rm -f /etc/systemd/system/halo-led-temp.service /usr/local/bin/halo-led-temp.py
systemctl daemon-reload
echo "halo-party-mode removed; LED restored to its previous color."
