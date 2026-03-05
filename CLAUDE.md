# trAIns — Claude Code Skill for UK Train Times

## Overview

A Claude Code skill (`/trains`) that checks live UK train departures between two configurable stations. Uses the free Huxley2 API (National Rail Darwin proxy). No API key needed.

GitHub: `maxtattonbrown/trains-skill`

## Architecture

```
trains-skill/              ← GitHub repo (also submodule in MTBvault/Projects/)
├── SKILL.md               ← Skill definition (loaded by Claude Code)
├── scripts/departures.py  ← TUI display script (ANSI board + split-flap animation)
├── README.md              ← Public README
├── demo.gif               ← Animated GIF of the board (captured via Playwright + HTML recreation)
└── screenshot.png         ← Legacy, can be removed

~/.claude/skills/trains/   ← Where the skill actually runs from (symlinked or copied)
~/.claude/trains/           ← Runtime data
├── config.json            ← Station pair + display preferences
├── timetable.json         ← Cached baseline timetable
└── platforms.json         ← Auto-logged platform assignments over time
```

The repo and `~/.claude/skills/trains/` must be kept in sync manually (copy files after edits).

## Key Design Decisions

- **Terminal.app popup for animation**: Claude Code's Bash tool buffers output, so split-flap animation can't play inline. Solution: `osascript` opens a Terminal.app window where the animation runs live. A compact inline summary also appears in the conversation.
- **Minimal table layout**: Board shows DEP/ARR/MINS/TYPE columns. No repeated destination. Fast trains amber, status only shown for disruptions. Width 52 chars.
- **Platform logging**: Every query silently logs platform assignments to `platforms.json` (keyed by route+time, last 30 observations). Future feature: "usually plat X" hints.
- **Filter + sort**: `--fast`/`--semi`/`--stopping` filters; `--sort arrive` reorders by arrival time. Config or CLI flags.

## Known Issues / TODO

- **Terminal.app opens on wrong desktop**: `osascript` opens Terminal wherever it last was, not the current Space. Fix: add `activate` before `do script` to bring it forward. Not yet implemented.
- **`render_clean()` not updated**: The clean theme still uses the old wide layout with destination column. Needs updating to match the new minimal design.
- **SKILL.md inline board format outdated**: The box-drawing example in SKILL.md still shows the old layout with destination column. Should be updated to match the new DEP/ARR/MINS/TYPE format.
- **`screenshot.png` is stale**: Old screenshot from before redesign. Can be deleted (README now references `demo.gif`).
- **No tests**: The skill has no test suite. `departures.py` could use unit tests for `parse_services`, `calc_journey_mins`, `route_type`, `format_status`.
- **fetch.py not in repo**: The SKILL.md references `~/.claude/skills/trains/scripts/fetch.py` but this file isn't in the GitHub repo.

## API

Base: `https://national-rail-api.davwheat.dev` (Huxley2 community instance, no auth)

- Departures: `/departures/{from}/to/{to}?expand=true`
- Delays: `/delays/{from}/to/{to}/60`
- Limitation: only sees ~4 hours ahead (Darwin constraint)

## Config

`~/.claude/trains/config.json`:
```json
{
  "home": {"name": "Leighton Buzzard", "crs": "LBZ"},
  "work": {"name": "London Euston", "crs": "EUS"},
  "theme": "board",
  "sort": "depart",
  "filter": null
}
```

## GIF Capture Process

The demo GIF is an HTML recreation of the terminal output, not a direct terminal capture (screencapture is blocked by sandbox). Process:
1. Build `/tmp/trains-demo-v2.html` matching the real terminal layout with JS split-flap animation
2. Use Playwright (installed in `/tmp/trains-gif-capture/`) to screenshot frames at 80ms intervals
3. Stitch with ffmpeg into a 12fps GIF (~84KB)

To regenerate: update the HTML with current train data, run the capture script.
