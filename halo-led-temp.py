#!/usr/bin/env python3
"""
halo-led-temp.py — pulse the AMD Ryzen AI Halo light bar, colored by CPU/GPU temp.

Cool = slow blue breathing; hot = fast red breathing. Uses the hotter of the
amdgpu 'edge' and k10temp 'Tctl' sensors. Restores the original LED state on exit.
Requires root (sysfs writes). Uses the amd_halo_led multicolor LED interface.

  sudo ./halo-led-temp.py            # run
  sudo ./halo-led-temp.py --verbose  # also print temps / write latency
"""
import glob, math, os, signal, sys, time

# (temp_C, (R, G, B)) — colors are interpolated between these stops
# Tuned for this box: ~40C idle (room ~20C/68F), ~85C sustained load, 104C peak seen
STOPS = [
    (40, (0, 60, 255)),     # idle: blue
    (55, (0, 200, 200)),    # light load: teal
    (70, (0, 255, 60)),     # moderate: green
    (82, (255, 200, 0)),    # heavy load: yellow
    (92, (255, 90, 0)),     # very hot: orange
    (102, (255, 0, 0)),     # near peak: red
]
SLOW_PERIOD, FAST_PERIOD = 4.0, 0.8   # seconds per breath (cool -> hot)
MIN_BRIGHT = 0.12                     # floor so the bar never fully goes dark
GAMMA = 2.0                           # perceptual correction so the fade looks even
FRAME = 0.05                          # target 20 fps
TEMP_POLL = 1.0                       # re-read temperature every second
VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv


def find_led():
    if os.environ.get("HALO_LED"):
        return os.environ["HALO_LED"]
    cands = [os.path.dirname(p) for p in glob.glob("/sys/class/leds/*/multi_intensity")]
    halo = [c for c in cands if "halo" in c.lower()]
    if halo or cands:
        return (halo or cands)[0]
    sys.exit("No multicolor LED found in /sys/class/leds (is amd_halo_led loaded?)")


def find_sensors():
    """Return {label: path} for the GPU edge and CPU Tctl sensors."""
    found = {}
    for hw in glob.glob("/sys/class/hwmon/hwmon*"):
        try:
            name = open(f"{hw}/name").read().strip()
        except OSError:
            continue
        if name == "amdgpu":
            found["gpu"] = f"{hw}/temp1_input"      # 'edge'
        elif name == "k10temp":
            found["cpu"] = f"{hw}/temp1_input"      # 'Tctl'
    if not found:
        sys.exit("No amdgpu or k10temp hwmon sensor found")
    return found


def read_temps(sensors):
    temps = {}
    for label, path in sensors.items():
        try:
            temps[label] = int(open(path).read()) / 1000.0
        except (OSError, ValueError):
            pass
    return temps


def temp_to_color(t):
    if t <= STOPS[0][0]:
        return STOPS[0][1]
    for (t0, c0), (t1, c1) in zip(STOPS, STOPS[1:]):
        if t <= t1:
            f = (t - t0) / (t1 - t0)
            return tuple(round(a + (b - a) * f) for a, b in zip(c0, c1))
    return STOPS[-1][1]


def temp_to_period(t):
    lo, hi = STOPS[0][0], STOPS[-1][0]
    f = min(max((t - lo) / (hi - lo), 0), 1)
    return SLOW_PERIOD + (FAST_PERIOD - SLOW_PERIOD) * f


def write(path, value):
    with open(path, "w") as f:
        f.write(value)


def main():
    led, sensors = find_led(), find_sensors()
    order = open(f"{led}/multi_index").read().split()      # e.g. red green blue
    max_b = int(open(f"{led}/max_brightness").read())
    idx = {"red": 0, "green": 1, "blue": 2}
    print(f"LED: {led} ({' '.join(order)}), sensors: {sensors}", flush=True)

    # remember original state so we can put it back on exit
    orig_int = open(f"{led}/multi_intensity").read().strip()
    orig_bri = open(f"{led}/brightness").read().strip()
    if not os.access(f"{led}/brightness", os.W_OK):
        sys.exit(f"Cannot write {led}/brightness — run with sudo (or as a member of halo-lp)")

    def restore():
        try:
            write(f"{led}/multi_intensity", orig_int)
            write(f"{led}/brightness", orig_bri)
        except OSError as e:
            print(f"could not restore LED: {e}", file=sys.stderr)

    def on_signal(*_):
        sys.exit(0)          # unwinds into the finally below, which restores
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    phase, last_poll, temp = 0.0, 0.0, 0.0
    last_color, last_level = None, None
    prev = time.monotonic()
    try:
        while True:
            now = time.monotonic()
            dt, prev = now - prev, now

            if now - last_poll >= TEMP_POLL:
                temps = read_temps(sensors)
                if temps:
                    temp = max(temps.values())
                last_poll = now
                if VERBOSE:
                    print(f"temps={temps} -> {temp:.1f}C color={temp_to_color(temp)}", flush=True)

            t0 = time.monotonic()
            rgb = temp_to_color(temp)
            if rgb != last_color:
                # STOPS are 0-255; the driver rejects any channel above max_brightness
                # (100 here) once scaled by brightness, so rescale to 0..max_b
                vals = [str(round(rgb[idx[ch]] * max_b / 255)) if ch in idx else "0"
                        for ch in order]
                write(f"{led}/multi_intensity", " ".join(vals))
                last_color, last_level = rgb, None   # force brightness re-apply

            # sine "breathing" curve, speed set by temperature; uses real elapsed time
            phase = (phase + dt / temp_to_period(temp)) % 1.0
            wave = 0.5 - 0.5 * math.cos(2 * math.pi * phase)
            level = MIN_BRIGHT + (1 - MIN_BRIGHT) * wave ** GAMMA
            b = round(level * max_b)
            if b != last_level:
                write(f"{led}/brightness", str(b))
                last_level = b
            spent = time.monotonic() - t0
            if VERBOSE and spent > FRAME:
                print(f"slow LED write: {spent*1000:.0f} ms", flush=True)

            time.sleep(max(0.0, FRAME - (time.monotonic() - now)))
    finally:
        restore()


if __name__ == "__main__":
    main()
