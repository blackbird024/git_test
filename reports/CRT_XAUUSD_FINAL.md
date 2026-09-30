# CRT XAUUSD — FINAL REPORT

## VERDICT

**NOT EVALUATED — no dataset.** None of the three allowed verdicts (ROBUST EDGE / PROMISING BUT
INSUFFICIENT / NO ROBUST EDGE) can be issued without data. No numbers in this repository come from
market data; no data was fabricated.

Reason: `Dataset metadata not found: /home/user/git_test/data/XAUUSD_M15.meta.json. See docs/DATA_REQUIREMENTS.md`

Pre-registration version: `2.0.0`.

What is needed: see `docs/DATA_REQUIREMENTS.md`. Once `data/XAUUSD_M15.csv` and
`data/XAUUSD_M15.meta.json` exist, run:

```
python -m crt_xauusd.run            # TRAIN + VALIDATION only
python -m crt_xauusd.run --unlock-test   # only after the rules are frozen
```

Rules that will be evaluated: `docs/PREREGISTRATION.md`. Audit of the repository: `docs/AUDIT.md`.
