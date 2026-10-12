# MMM.FUN Level Up · prototype

Interactive prototype of the Mmmmmm.fun flow, built from the `MMM.pen` frames in pen.dev.

**Live:** https://mmm-fun-prototype.vercel.app

## What's in it
- **Level 1 · McDoughnald's** — first visit → Load FLY sheet → first order → printed receipt (three.js paper print + tear) → authed home
- **Promotions** to STARBAGS ($100), SWEETGREED ($1K), CARBONUS ($10K) and NOBULL ($100K), each with its own home
- **mmm.supply** — the side-scrolling clothesline merch lander (wheel / drag / arrow keys)
- A demo dock to step through levels (`←` `→`, `H` hides it)

## Files
- `index.html` — the built, self-contained prototype (deployed to Vercel as-is)
- `src/shell.html` — interaction layer, animations and demo dock
- `src/build.py` — merges the pen.dev HTML exports into `shell.html` and inlines `src/assets`
- `src/assets/` — compressed images used by the screens

The page loads three.js r128 and html2canvas 1.4.1 from cdnjs; everything else is inline.
