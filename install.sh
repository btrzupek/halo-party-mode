#!/usr/bin/env bash
# Install halo-party-mode as a systemd service on an AMD Ryzen AI Halo.
# Run on the Halo itself:  sudo ./install.sh
set -euo pipefail

LED="${HALO_LED:-/sys/class/leds/amd_halo:multicolor:status}"
HERE="$(cd "$(dirname "$0")" && pwd)"
UNIT=/etc/systemd/system/halo-led-temp.service

if [[ $EUID -ne 0 ]]; then
    echo "Please run as root: sudo $0" >&2
    exit 1
fi
if [[ ! -e "$LED/multi_intensity" ]]; then
    echo "LED not found at $LED — is the amd_halo_led kernel module loaded?" >&2
    echo "(set HALO_LED=/sys/class/leds/<name> to override)" >&2
    exit 1
fi

install -m755 "$HERE/halo-led-temp.py" /usr/local/bin/halo-led-temp.py
install -m644 "$HERE/halo-led-temp.service" "$UNIT"

# The service runs unprivileged in the group that owns the LED files (halo-lp on
# the stock Halo image). If the files are root-only, fall back to running as root.
group="$(stat -c %G "$LED/brightness")"
if [[ "$group" == "root" ]] || [[ ! -w "$LED/brightness" ]]; then
    echo "LED files are root-only; the service will run as root."
    sed -i -e '/^DynamicUser=/d' -e '/^SupplementaryGroups=/d' -e '/^# LED sysfs/d' "$UNIT"
else
    sed -i "s/^SupplementaryGroups=.*/SupplementaryGroups=$group/" "$UNIT"
fi
if [[ -n "${HALO_LED:-}" ]]; then
    sed -i "/^\[Service\]/a Environment=HALO_LED=$HALO_LED" "$UNIT"
fi

systemctl daemon-reload
systemctl enable --now halo-led-temp.service
systemctl restart halo-led-temp.service
echo "halo-party-mode installed and running:"
systemctl --no-pager --lines=0 status halo-led-temp.service
