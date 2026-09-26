# halo-party-mode

Turn the light bar on the **AMD Ryzen AI Halo** into a live temperature gauge.

The LED breathes gently in a color that tracks how hot the machine is: slow and blue when
idle, speeding up and warming through green and yellow to fast red when the CPU or GPU is
working hard.

| Chip temp | Color | Breath |
|---|---|---|
| 40 °C (idle) | 🔵 blue | 4.0 s |
| 55 °C | 🩵 teal | 3.2 s |
| 70 °C | 🟢 green | 2.5 s |
| 82 °C (heavy load) | 🟡 yellow | 1.8 s |
| 92 °C | 🟠 orange | 1.3 s |
| 102 °C+ | 🔴 red | 0.8 s |

Colors blend smoothly between these points. It uses whichever is hotter, the GPU
(`amdgpu` edge) or the CPU (`k10temp` Tctl).

## Requirements

- An AMD Ryzen AI Halo (tested on the `RAH-001` developer platform) running Linux
- The `amd_halo_led` kernel module (ships with AMD's Halo image). Check with:
  ```bash
  ls /sys/class/leds/amd_halo:multicolor:status
  ```
- Python 3 (standard library only, no pip installs)
- systemd, for running it as a service

## Quick start

On the Halo:

```bash
git clone https://github.com/btrzupek/halo-party-mode.git
```
```bash
cd halo-party-mode && sudo ./install.sh
```

That's it. The light bar starts breathing right away and keeps doing so after reboots.

### Installing from another machine over SSH

Replace `halo` with your Halo's SSH host name or `user@ip`:

```bash
ssh halo mkdir -p halo-party-mode && scp halo-led-temp.py halo-led-temp.service install.sh uninstall.sh halo:halo-party-mode/
```
```bash
ssh -t halo 'cd ~/halo-party-mode && sudo ./install.sh'
```

## Try it without installing

Run it in the foreground for a test. `-v` prints the temperatures and chosen color every
second. Press Ctrl-C to stop; the LED goes back to its previous color.

```bash
sudo ./halo-led-temp.py -v
```

Or run it for a fixed time:

```bash
sudo timeout -s INT 20 ./halo-led-temp.py -v
```

## Managing the service

| What | Command |
|---|---|
| Is it running? | `systemctl status halo-led-temp` |
| Watch its log | `journalctl -u halo-led-temp -f` |
| Stop for now (restores original color) | `sudo systemctl stop halo-led-temp` |
| Start again | `sudo systemctl start halo-led-temp` |
| Restart after editing settings | `sudo systemctl restart halo-led-temp` |
| Don't start at boot | `sudo systemctl disable halo-led-temp` |
| Remove completely | `sudo ./uninstall.sh` |

Peek at what the LED is being told to do (should change every fraction of a second):

```bash
cd /sys/class/leds/amd_halo:multicolor:status && watch -n0.3 'cat multi_intensity brightness'
```

## Customizing

All settings are at the top of `halo-led-temp.py` (installed to
`/usr/local/bin/halo-led-temp.py`):

| Setting | What it does | Default |
|---|---|---|
| `STOPS` | Temperature (°C) → color (R, G, B, 0–255) points | 40 °C blue … 102 °C red |
| `SLOW_PERIOD` | Seconds per breath at the coolest stop | `4.0` |
| `FAST_PERIOD` | Seconds per breath at the hottest stop | `0.8` |
| `MIN_BRIGHT` | Dimmest point of each breath (0–1); keeps it from going dark | `0.12` |
| `GAMMA` | Fade shape; higher lingers longer in the dim part | `2.0` |
| `FRAME` | Seconds between updates (0.05 = 20 fps) | `0.05` |
| `TEMP_POLL` | Seconds between temperature reads | `1.0` |

The defaults are tuned for a Halo that idles around 40 °C, sits around 85 °C under sustained
load and peaks near 104 °C. If yours runs cooler or hotter, move the `STOPS` temperatures.

After editing, reinstall (`sudo ./install.sh`) or copy the file to `/usr/local/bin/` and
restart the service.

To use a different LED, set `HALO_LED` to its sysfs folder before installing:

```bash
sudo HALO_LED=/sys/class/leds/<name> ./install.sh
```

## How it works

The `amd_halo_led` driver exposes the light bar as a standard Linux multicolor LED:

- `multi_intensity` sets the color as three numbers (red green blue)
- `brightness` sets the overall level, 0–100

The script reads the temperature once a second, picks a color from `STOPS`, and writes
`brightness` 20 times a second along a gamma-corrected sine wave to make the "breathing"
effect.

**Gotcha:** this LED's color channels run **0–100, not 0–255**. The driver multiplies each
channel by `brightness / 100` and silently rejects the whole update if any channel ends up
above 100. With 0–255 colors the LED works while dim and then drops out above ~39%
brightness, looking like "pulse, then dark". The script scales colors to the LED's range
for you.

**Permissions:** on the stock Halo image the LED files belong to the `halo-lp` group, so the
service runs as an unprivileged throwaway user in that group (`DynamicUser=yes`). If the files
are root-only on your system, `install.sh` switches the service to run as root.

**AMD Halo Center:** the Halo Center app (`halo-lp`) only writes the LED when you change the
color in its UI. While this service runs, such a change is overwritten within a second. Stop
the service to use a Halo Center color again.

## Troubleshooting

- **`No multicolor LED found`**: the `amd_halo_led` module isn't loaded. Try
  `sudo modprobe amd_halo_led`.
- **`Cannot write .../brightness`**: run with `sudo`, or add yourself to the group that
  owns the LED files (`ls -l /sys/class/leds/amd_halo:multicolor:status/`).
- **The LED stays one color and doesn't breathe**: check `systemctl status halo-led-temp`
  and `journalctl -u halo-led-temp`.
- **It's always red/orange**: your machine runs hotter than the defaults assume; raise the
  `STOPS` temperatures.

## License

[MIT](LICENSE)
