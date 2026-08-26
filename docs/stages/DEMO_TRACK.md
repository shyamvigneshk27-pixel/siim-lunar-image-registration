# Demo Track — September 2 internal hackathon

**Classification: DEMO-CRITICAL.** **Scientific experimentation is stopped.** REAL-DATA-04
was the final causal experiment; this track is now the only active work.

*(Updated 2026-08-26: REAL-DATA-05 ran afterwards as the pre-registered replication of
REAL-DATA-04 and closed **UNRESOLVED, BY DATA AVAILABILITY** — its screen returned zero
admissible frames, so no image byte was fetched and no registration was run. **It produced no
number this demo shows or could show**, and the three real edges below are unchanged. Its one
consequence for the demo is a wording constraint, already satisfied: frame identity is
**substantially weakened, not conclusively refuted** (D-040-N1), and the page's fixed
`CAUSAL_SUMMARY` only ever claims that outcome **tracks** illumination rather than frame
identity, which remains within the evidence.)*

**Freeze: 2026-09-01.** After freeze: bug fixes, reliability, UI polish, docs and
rehearsal only. No algorithm, dependency, architecture or dataset changes.

---

## Launch

```bash
python scripts/run_demo.py            # then open http://127.0.0.1:8000/
python scripts/run_demo.py --open     # and open the browser for you
```

One command. No environment variables, no build step, **no network access**. The launcher
puts `src/` on the path itself and prints a pre-flight check of the files the real-data
cases need before it starts serving — a missing artefact is something to find out about
with the projector still off.

## Architecture, and why it is this small

FastAPI (already installed) + **vanilla HTML/JS, no build step**. React/Vite was
considered and rejected: it costs a day of toolchain setup and adds a demo-day failure
mode for no scientific value. §15 says prefer simple and local; this is that.

```
src/siim/demo/
  verdict.py          MATCH -> REGISTER -> VERIFY -> EXPLAIN. The differentiator.
  evidence.py         real-data cases, assembled from recorded experiment artefacts
  api.py              FastAPI: /api/scenarios, /api/run, /api/evidence/illumination
  static/index.html   single page, zero dependencies
  assets/             tile previews + certified correspondence overlays
scripts/
  run_demo.py         one-command launch with a pre-flight check
  build_demo_assets.py  rebuilds assets/, refusing to write unless they match
```

## Where the demo's numbers come from

| Case set | `computation` | Source |
|---|---|---|
| **Real LRO NAC** | `recorded_artefact` | `experiments/REAL-DATA-0{3,4}/*.json`, read at request time |
| **Synthetic** | `live` | generated and registered in the request |

**Every scientific number the real-data page displays is read out of a file under
`experiments/`, and the page prints the path it came from.** Nothing is recomputed for
display. A demo that re-derives its own numbers can drift from the stage report that
justifies them, and then the two disagree in front of an audience.

### The one thing that cannot be read, and how it is certified

The recorded artefact stores **1656**, not the 1656 point coordinates — so the
correspondence overlay cannot be drawn from it. `scripts/build_demo_assets.py` re-runs the
identical seeded pipeline to recover the coordinates and **refuses to write anything unless
every recomputed statistic is bit-identical to the recorded one**, on all three edges:
keypoint counts, putative, inliers, inlier ratio, fit RMSE and all six transform-matrix
entries. `evidence.py` re-checks the correspondence and inlier counts again at load time,
so the guarantee is a property of what is on disk now, not of the builder having run.

Verified 2026-08-26: **all 3 edges reproduced the recorded artefact exactly.**

## The demo sequence

Four numbered steps, in this order, on every case:

| Step | The question on screen |
|---|---|
| **1** | Do these images actually see the same ground? |
| **2** | Can the images establish a consistent transform? |
| **3** | Do independent signals agree? |
| **4** | So — should this alignment be trusted? |

### Real case 1 — D → A, the success

| | |
|---|---|
| Δincidence | **11.73°** |
| Overlap (confirmed **before** the matcher) | **71.30 %** min, p5 68.01 % |
| Putative → inliers | 1759 → **1656** (ratio 0.9414) |
| Coverage gap / occupancy | 0.1033 / **1.000** |
| fit RMSE | 0.8779 px — *reported, excluded* |
| Outcome | **SUCCEED** |
| Verdict | **INCONCLUSIVE / moderate** — see below |

### Real case 2 — B → D, the failure and the central moment

| | |
|---|---|
| Δincidence | **51.54°** |
| Overlap (confirmed **before** the matcher) | **70.35 %** min, p5 67.38 % |
| Putative → inliers | 29 → **3** (ratio 0.1034) |
| Coverage gap / occupancy | 0.4268 / 0.047 |
| fit RMSE | **1.885e-13 px** — *reported, excluded* |
| Outcome | **FAIL** |
| Verdict | **REJECTED / none** |

**The RMSE trap**, staged as four timed beats with a replay button:

```
The fit RMSE looks flawless          1.885e-13 px
        ↓
but only 3 of 29 correspondences     3 / 29 inliers
        ↓
coverage is poor                     gap 0.4268 · occupancy 0.047
        ↓
verdict                              ✕ REJECTED
```

**The RMSE is shown unaltered and never hidden.** It is then structurally excluded — ROC AUC
0.4947 as a failure detector, a coin flip. Ranking these three real edges by fit RMSE would
put the **rejected** one first, and there is a test that says so.

### Why the success case is not green

The overlap gate proves shared ground, so **B → D's failure cannot be blamed on
non-overlapping tiles** — the two decisive edges are matched to **0.95 percentage points**,
and the control A → B has the *most* overlap of the three (97.87 %) and still fails.

And on the success case the verdict engine says **INCONCLUSIVE, not VERIFIED**. That is
correct and deliberate: loop closure is the only check that catches a coherent wrong answer,
and it did not run for this edge — the triplet it belongs to has two failing legs, so
attributing that 943.75 px residual to the succeeding edge would be false. **The verdict
criteria were not adjusted to turn it green.** The page says *"No evidence against, but the
decisive check was not run"* and explains why, which is REAL-DATA-04 §15 Q3 (*corroborated,
never verified — class B*) shown rather than described.

The synthetic `easy_same_sun` case **does** reach VERIFIED / high, so the audience sees the
engine can say yes when the evidence is there. That is what makes the real-data
INCONCLUSIVE mean something instead of looking like a limitation of the code.

### Real case 3 — A → B, the replication control

39.81°, 97.87 % overlap, **7 inliers**, FAIL. The same two frames as REAL-DATA-03, at a
ground window 10.8 km away — an independent replication of that failure. Reported at 7
against a threshold of 8, next to the threshold, rather than rounded away.

### The cross-edge causal panel

All six measured real edges, on a log dot plot with the reject rule drawn as a reference
line and the un-probed 11.73°–38.85° band shaded:

| edge | stage | Δinc | overlap | inliers | outcome |
|---|---|---|---|---|---|
| B → C | RD-03 | 0.96° | 85.00 % | 5365 | ✓ SUCCEED |
| **D → A** | **RD-04** | **11.73°** | 71.30 % | **1656** | **✓ SUCCEED** |
| C → A | RD-03 | 38.85° | 82.72 % | 4 | ✕ FAIL |
| A → B | RD-03 | 39.81° | 97.12 % | 4 | ✕ FAIL |
| A → B | RD-04 | 39.81° | 97.87 % | 7 | ✕ FAIL |
| **B → D** | **RD-04** | **51.54°** | 70.35 % | **3** | **✕ FAIL** |

What the page is allowed to say, fixed as one constant so the UI cannot widen it:

> *"Across the measured real-data edges, registration outcome tracks illumination difference
> rather than frame identity."*
> **Scope: LRO NAC · Mare Serenitatis · five frames · two ground windows · incidence only,
> NOT azimuth-controlled.**

Both the separation claim and the frame-identity claim are computed from the rows, not
typed — and tested.

### Controlled synthetic adversarial case — preserved, and labelled

`coherent_wrong`, live: fit RMSE **0.1497 px**, **1273** inliers, coverage gap **0.0735** —
every conventional signal excellent — loop closure **63.998 px**, verdict **REJECTED**,
ground truth confirms **63.99 px** wrong. Banner: *CONTROLLED SYNTHETIC ADVERSARIAL CASE*.
It demonstrates the second principle: **low residual and many correspondences can still be
insufficient without independent loop-closure evidence.** Synthetic ground truth is shown
only here, labelled as available *only* because the terrain is synthetic.

## Confidence is evidence, not a number

`verdict.py` returns an ordinal band plus the named evidence behind it. There is no invented
`0.97`. Each signal carries its measured weight:

| Signal | Weight | Basis |
|---|---|---|
| `loop_error_px` | **decisive** | Only estimator that detects a coherent wrong solution — 1.000/0.000 (EXP-003, ADR-0011) |
| `n_inliers` | **decisive against**, weak for | `<= 8` at recall 1.000 (EXP-002) — but FPR 0.369 in mixed regime (EXP-003) |
| `coverage_max_gap` | strong | Bounds worst-case local error (ADR-0006) |
| `inlier_ratio` | supporting | Self-consistency; misses 8.7 % of failures |
| `fit_rmse` | **excluded** | ROC AUC 0.4947 — chance. Reported, never used |
| `held_out_residual`, `cycle_consistency` | **excluded** | Detection 0.200 / blind to symmetric errors |

## Colour, and why it is not green-vs-red

Registration outcome is encoded **blue (succeed) / red (fail)**, not green/red: green vs red
measures CVD ΔE **4.1** on this surface — a fail — while blue vs red measures **25.7** and
clears every check of the palette validator. Outcome also always carries a **glyph and a
word**, so colour never carries the meaning alone. Verdict blocks use the reserved status
palette with an icon and the status word.

## Removed, deliberately

The old `real_lro_nac` scenario is **gone**. It showed REAL-DATA-01's pair, which
REAL-DATA-02 later measured to be **22.75 km apart, sharing 0.0000 km²** (E-028, E-029).
Demonstrating a registration failure on tiles that do not overlap would show a failure whose
cause is the acquisition, not the matcher — exactly the confusion REAL-DATA-02 and -03
existed to remove. A test asserts it is not offered.

## Status

| Item | State |
|---|---|
| Verdict engine + 11 tests | **done** |
| FastAPI backend, 3 endpoints | **done**, verified live |
| Presentation UI, 4-step sequence | **done** — verified in-browser at 1680×1050 |
| Overlap-first visualisation, with ground footprints | **done** |
| D → A real success | **done** |
| B → D real failure + staged RMSE-trap reveal | **done** |
| Cross-edge illumination panel | **done** |
| Synthetic adversarial case preserved and labelled | **done** |
| REAL / SYNTHETIC badges everywhere | **done** |
| One-command launch, no network | **done** |
| Tests | **441 passed, 2 skipped** (was 398) |
| Chandrayaan-2 / multi-modal | **blocked** on ISSDC registration — and claimed nowhere |

## Deliberately not claimed

Multi-modal capability · Chandrayaan-2 anything · ground-truth-verified real registration ·
Sun-**azimuth** invariance · illumination as a universal cause of registration failure ·
a located illumination threshold (bracketed only to 11.73°–38.85°) · any learned matcher ·
any EXP-004 result. A test scans every real-data response for these terms and requires each
occurrence to sit next to a negation.
