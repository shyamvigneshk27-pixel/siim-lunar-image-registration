# Demo Track — September 2 internal hackathon

**Classification: DEMO-CRITICAL.** Runs in parallel with EXP-004; does not wait for it.

**Freeze: 2026-09-01.** After freeze: bug fixes, reliability, UI polish, docs and
rehearsal only. No algorithm, dependency, architecture or dataset changes.

---

## Architecture, and why it is this small

FastAPI (already installed) + **vanilla HTML/JS, no build step**. React/Vite was
considered and rejected: it costs a day of toolchain setup and adds a demo-day
failure mode for no scientific value. §15 says prefer simple and local; this is that.

```
src/siim/demo/
  verdict.py          MATCH -> REGISTER -> VERIFY -> EXPLAIN. The differentiator.
  api.py              FastAPI: /api/scenarios, /api/run
  static/index.html   single page, zero dependencies
```

Run: `PYTHONPATH=src python -m uvicorn siim.demo.api:app --port 8000` → `http://127.0.0.1:8000`

## The honesty contract, enforced in the response shape

Every `/api/run` response carries, and the UI displays:

| Field | Meaning |
|---|---|
| `computation` | `"live"` or `"cached"` — nothing cached can be shown as live (§16) |
| `data_source` | `"synthetic"` or `"real_lro_nac"` |
| `adversarial_construction` | true when the failure was deliberately constructed, with a note saying so |
| `ground_truth.available` | true only for synthetic data, with a note that real imagery has none |
| `verdict.excluded` | the signals structurally barred from the verdict, each with its disqualifying measurement |

## Confidence is evidence, not a number

`verdict.py` returns an ordinal band (`high`/`moderate`/`low`/`none`) plus the named
evidence behind it. There is no invented `0.97` — §12 forbids it and the project has
not earned that calibration. Each signal carries its measured weight:

| Signal | Weight | Basis |
|---|---|---|
| `loop_error_px` | **decisive** | Only estimator that detects a coherent wrong solution — 1.000/0.000 (EXP-003, ADR-0011) |
| `n_inliers` | **decisive against**, weak for | `<= 8` at recall 1.000 (EXP-002) — but FPR 0.369 in mixed regime (EXP-003), so a high count proves little |
| `coverage_max_gap` | strong | Bounds worst-case local error (ADR-0006) |
| `inlier_ratio` | supporting | Self-consistency; misses 8.7% of failures |
| `fit_rmse` | **excluded** | ROC AUC 0.4947 — chance. Reported, never used |
| `held_out_residual`, `cycle_consistency` | **excluded** | Detection 0.200 / blind to symmetric errors |

## The wow case — measured, not manufactured

`coherent_wrong`: correspondences displaced by exactly one crater spacing, the failure
EXP-001 measured on generated terrain. **Live, verified 2026-08-24:**

| | `easy_same_sun` | `coherent_wrong` |
|---|---|---|
| fit RMSE | 0.147 px | **0.150 px** — looks excellent |
| inliers | 1258 | **1273** — looks excellent |
| coverage gap | 0.069 | **0.074** — looks excellent |
| **loop closure** | **0.008 px** | **63.998 px** |
| **verdict** | **VERIFIED / high** | **REJECTED / none** |
| true error (GT) | 0.00 px | **63.99 px** |

Every conventional signal says the wrong answer is excellent. Loop closure is the only
one that catches it. That is the story, and it is real measured behaviour.

**Labelled honestly:** this is a *controlled synthetic adversarial construction*, declared
in the API response and shown as a banner in the UI. If a real LRO NAC pair produces a
natural failure it replaces this; until then the label stands.

## Status

| Item | State |
|---|---|
| Verdict engine + 11 tests | **done** |
| FastAPI backend, 2 endpoints | **done**, verified live |
| Single-page UI | **done** — images, correspondence overlay, verdict, evidence table |
| Wow case | **done**, measured |
| Real LRO NAC in the demo | **not yet** — labels only; tiles not ingested |
| Registration slider / before-after overlay | **not yet** |
| Chandrayaan-2 / multi-modal | **blocked** on ISSDC registration |

## Deliberately not claimed

Multi-modal capability · Chandrayaan-2 anything · real-data validation ·
Sun-**azimuth** invariance on real data (azimuth is not in the archive metadata — E-020) ·
scale invariance beyond the tested range.
