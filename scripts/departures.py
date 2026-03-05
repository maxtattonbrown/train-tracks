# ABOUTME: Displays live UK train departures in terminal with theme support.
# ABOUTME: Reads JSON from stdin. Args: DEST_CRS [--theme board|clean] [--animate]

import json
import sys
import re
import time
import random
import os
from datetime import datetime

# ── ANSI codes ──────────────────────────────────────────────────
BG  = "\033[40m";   RS = "\033[0m"
AM  = "\033[33m";   WH = "\033[97m";  DM = "\033[90m"
GR  = "\033[32m";   RD = "\033[91m";  BD = "\033[1m"
CLR = "\033[2J\033[H"  # clear screen + home cursor
HIDE_CUR = "\033[?25l"
SHOW_CUR = "\033[?25h"

FLIP_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:.- "

_ANSI_RE = re.compile(r'\033\[[0-9;]*m')


def strip_ansi(s):
    """Remove ANSI escape codes from a string."""
    return _ANSI_RE.sub('', s)


def vlen(s):
    """Visible length of string, stripping ANSI codes."""
    return len(strip_ansi(s))


def hhmm_to_mins(s):
    """Parse 'HH:MM' to total minutes since midnight."""
    h, m = map(int, s.split(":"))
    return h * 60 + m


def format_status(std, etd, is_cancelled):
    if etd == "On time" and not is_cancelled:
        return ("On time", "ok")
    if etd == "Cancelled" or is_cancelled:
        return ("Cancelled", "bad")
    if etd == "Delayed":
        return ("Delayed", "bad")
    if ":" in str(etd):
        try:
            if hhmm_to_mins(etd) > hhmm_to_mins(std):
                return (f"Exp {etd}", "bad")
            return ("On time", "ok")
        except ValueError:
            return (etd, "neutral")
    return (etd, "neutral")


def get_service_stops(service, dest_crs):
    """Get arrival time and intermediate calling points in a single pass."""
    stops = []
    for cp_list in service.get("subsequentCallingPoints", []):
        for cp in cp_list.get("callingPoint", []):
            if cp.get("crs") == dest_crs:
                return cp.get("st", ""), stops
            stops.append(cp.get("locationName", ""))
    return "", stops


def calc_journey_mins(dep, arr):
    """Calculate journey time in minutes from HH:MM strings."""
    try:
        return hhmm_to_mins(arr) - hhmm_to_mins(dep)
    except (ValueError, AttributeError):
        return None


def route_type(calling):
    """Classify route: 'fast' (0 stops), 'semi' (1-3), 'stopping' (4+)."""
    n = len(calling)
    if n == 0:
        return "fast"
    elif n <= 3:
        return "semi"
    return "stopping"


def parse_services(data, dest_crs):
    services = data.get("trainServices") or []
    rows = []
    for s in services[:8]:
        std = s.get("std", "?")
        etd = s.get("etd", "?")
        plat = s.get("platform", "") or ""
        op = s.get("operator", "?")
        op_code = s.get("operatorCode", "?")
        is_cancelled = s.get("isCancelled", False)
        arr, calling = get_service_stops(s, dest_crs)
        status_text, status_type = format_status(std, etd, is_cancelled)
        mins = calc_journey_mins(std, arr)
        rtype = route_type(calling)
        rows.append({
            "std": std, "arr": arr, "plat": plat,
            "status": status_text, "status_type": status_type,
            "op": op, "op_code": op_code, "calling": calling,
            "mins": mins, "route_type": rtype,
        })
    return rows


# ── CLEAN THEME ─────────────────────────────────────────────────

def render_clean(from_name, to_name, rows, now):
    W = 50

    def row(txt):
        return f"│ {txt:<{W}} │"

    print(f"┌─{'─' * W}─┐")
    print(row(f"{from_name} → {to_name}".center(W)))
    print(row(f"as of {now}".center(W)))
    print(f"├─{'─' * W}─┤")
    print(row(f"{'Dep':>5}  {'Arr':>5}  {'Plat':>4}  {'Status':<10} {'Op':<4}"))
    print(row(f"{'─' * 5}  {'─' * 5}  {'─' * 4}  {'─' * 10} {'─' * 4}"))

    if not rows:
        print(row("No services found".center(W)))
    else:
        for r in rows:
            plat = r["plat"] or "-"
            print(row(f"{r['std']:>5}  {r['arr']:>5}  {plat:>4}  {r['status']:<10} {r['op_code']:<4}"))

    print(f"├─{'─' * W}─┤")

    cancelled_n = sum(1 for r in rows if r["status_type"] == "bad")
    if cancelled_n:
        print(row(f"⚠  {cancelled_n} service(s) disrupted"))
    elif not rows:
        print(row("⚠  No services — check /trains disruptions"))
    else:
        print(row("✓  All services running on time"))
    print(f"└─{'─' * W}─┘")


# ── BOARD THEME ─────────────────────────────────────────────────

def board_line(content, w=52):
    vis = vlen(content)
    pad = max(0, w - vis)
    return f"{BG}{content}{' ' * pad}{RS}"


def render_board(from_name, to_name, rows, now, animate=False):
    W = 52

    def sep():
        print(board_line(f"{DM}{'─' * W}{RS}{BG}"))

    if animate:
        sys.stdout.write(HIDE_CUR)
        sys.stdout.flush()

    sep()
    print(board_line(""))
    print(board_line(f"  {BD}{WH}{from_name.upper()} → {to_name.upper()}{RS}{BG}"))
    print(board_line(f"  {DM}{now}{RS}{BG}"))
    print(board_line(""))
    sep()
    print(board_line(f"  {DM}DEP    ARR    MINS  TYPE{RS}{BG}"))
    sep()

    if not rows:
        print(board_line(""))
        print(board_line(f"  {DM}No services currently shown{RS}{BG}"))
        print(board_line(""))
    else:
        for i, r in enumerate(rows):
            mins_s = f"{r['mins']:>2}" if r["mins"] else " ?"

            # Route type: fast gets amber ⚡, semi gets dim "via X", stopping is unmarked
            if r["route_type"] == "fast":
                type_s = f"{AM}{BD}⚡ fast{RS}{BG}"
            elif r["route_type"] == "semi":
                via = r["calling"][0] if r["calling"] else ""
                # Shorten common station names
                via = via.replace(" Junction", " Jn")
                type_s = f"{DM}via {via}{RS}{BG}"
            else:
                type_s = f"{DM}stopping{RS}{BG}"

            # Platform: only show if assigned
            plat_s = f"  {DM}plat {WH}{r['plat']}{RS}{BG}" if r["plat"] else ""

            # Status: only show if NOT on time
            stat_s = f"  {RD}{r['status']}{RS}{BG}" if r["status_type"] == "bad" else ""

            # Build the row
            main = f"  {AM}{BD}{r['std']}{RS}{BG}   {WH}{r['arr']}{RS}{BG}    {DM}{mins_s}{RS}{BG}   {type_s}{plat_s}{stat_s}"

            if animate:
                flip_row(strip_ansi(main), main, W)
                time.sleep(0.08)
            else:
                print(board_line(main))

    sep()
    print(board_line(""))

    cancelled_n = sum(1 for r in rows if r["status_type"] == "bad")
    if cancelled_n:
        print(board_line(f"  {RD}▲ {cancelled_n} service(s) disrupted{RS}{BG}"))
    elif not rows:
        print(board_line(f"  {DM}No information available{RS}{BG}"))
    else:
        print(board_line(f"  {GR}● Good service{RS}{BG}"))

    print(board_line(""))
    sep()

    if animate:
        sys.stdout.write(SHOW_CUR)
        sys.stdout.flush()


def flip_row(target_plain, final_ansi, w):
    """Simulate split-flap display: characters flip through random letters before landing."""
    length = len(target_plain)
    # Each position has a random number of flips (2-5)
    flips_remaining = [random.randint(2, 5) for _ in range(length)]
    max_flips = max(flips_remaining)

    for frame in range(max_flips + 1):
        chars = []
        for j in range(length):
            if flips_remaining[j] <= frame:
                chars.append(target_plain[j])
            else:
                chars.append(random.choice(FLIP_CHARS))
        line = "".join(chars)

        # Visible length is deterministic: "  " prefix + line content
        vis = len(line) + 2
        pad = max(0, w - vis)
        sys.stdout.write(f"\r{BG}{AM}  {line}{RS}{BG}{' ' * pad}{RS}")
        sys.stdout.flush()
        time.sleep(0.04)

    # Final render with proper colours
    pad = max(0, w - vlen(final_ansi))
    sys.stdout.write(f"\r{BG}{final_ansi}{' ' * pad}{RS}\n")
    sys.stdout.flush()


# ── PLATFORM LOGGING ───────────────────────────────────────────

PLATFORM_LOG = os.path.expanduser("~/.claude/trains/platforms.json")


def log_platforms(from_station, dest_crs, rows):
    """Silently log platform assignments for future 'usually plat X' hints."""
    try:
        try:
            with open(PLATFORM_LOG) as f:
                log = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            log = {}

        today = datetime.now().strftime("%Y-%m-%d")
        day_of_week = datetime.now().strftime("%a")  # Mon, Tue, etc.

        for r in rows:
            if not r["plat"]:
                continue
            # Key: "EUS>LBZ:14:56" (route + scheduled time)
            key = f"{from_station}>{dest_crs}:{r['std']}"
            if key not in log:
                log[key] = []
            # Avoid duplicate entries for same day
            if not any(e["date"] == today for e in log[key]):
                log[key].append({
                    "date": today,
                    "day": day_of_week,
                    "plat": r["plat"],
                })
            # Keep last 30 observations per train
            log[key] = log[key][-30:]

        os.makedirs(os.path.dirname(PLATFORM_LOG), exist_ok=True)
        with open(PLATFORM_LOG, "w") as f:
            json.dump(log, f, indent=2)
    except Exception:
        pass  # Never let logging break the display


# ── MAIN ────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    # Parse flags
    theme = "board"
    animate = False
    dest_crs = None
    sort_by = "depart"
    filter_type = None

    i = 0
    while i < len(args):
        if args[i] == "--theme" and i + 1 < len(args):
            theme = args[i + 1]
            i += 2
        elif args[i] == "--animate":
            animate = True
            i += 1
        elif args[i] == "--sort" and i + 1 < len(args):
            sort_by = args[i + 1]  # "depart" or "arrive"
            i += 2
        elif args[i] == "--fast":
            filter_type = "fast"
            i += 1
        elif args[i] == "--semi":
            filter_type = "semi"
            i += 1
        elif args[i] == "--stopping":
            filter_type = "stopping"
            i += 1
        elif args[i] == "--filter" and i + 1 < len(args):
            filter_type = args[i + 1]
            i += 2
        elif dest_crs is None:
            dest_crs = args[i]
            i += 1
        else:
            i += 1

    if not dest_crs:
        print("Usage: curl -s '...' | departures.py DEST_CRS [--theme board|clean] [--animate] [--sort depart|arrive] [--fast|--semi|--stopping]")
        sys.exit(1)

    try:
        data = json.load(sys.stdin)
    except Exception:
        print(f"{RD}  Could not reach National Rail API{RS}")
        sys.exit(1)

    from_name = data.get("locationName", "?")
    to_name = data.get("filterLocationName", "?")
    now = datetime.now().strftime("%H:%M")
    rows = parse_services(data, dest_crs)

    # Quietly log platform observations
    log_platforms(from_name, dest_crs, rows)

    # Filter by route type
    if filter_type:
        rows = [r for r in rows if r["route_type"] == filter_type]

    # Sort by arrival time if requested
    if sort_by == "arrive":
        rows.sort(key=lambda r: r["arr"] or "99:99")

    if theme == "clean":
        render_clean(from_name, to_name, rows, now)
    else:
        render_board(from_name, to_name, rows, now, animate=animate)


if __name__ == "__main__":
    main()
