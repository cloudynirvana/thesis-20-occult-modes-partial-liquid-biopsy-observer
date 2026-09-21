# Hybrid occult mode switches under sparse delayed liquid-biopsy-style partial observers

**Thesis #20.** Computational research, set out in Nile University B.Sc. chapter order for handoff.

**Author:** Kelechi Emeka Ogbonna  
**Email:** kelechiogbonna300@gmail.com  
**GitHub:** https://github.com/cloudynirvana  
**Date:** 21 September 2026

**Depends on:** Thesis #4 (occult residual disease as hybrid switching modes) and Thesis #9 (multi-channel practical identifiability). The modes are not re-derived. The metabolic ranks are not copied.

Which hybrid occult mode switches remain practically identifiable when the observation map is a sparse, delayed liquid-biopsy-style partial observer rather than a full state schedule?

On one three-coordinate toy, a full state schedule separates proliferative continuation, quiescence, angiogenic pause, and immune-held latency. A dense burden channel still separates them while the two pauses have different burden balances. The sparse delayed scalar keeps those separations in that case, at a pairwise error of 0.051 for the two pauses, and it loses the pair when the pauses are given the same burden law: Fisher information for the contrast drops to 0, and the likelihood comparisons are unresolved ties. Switch time in an arm that never leaves the proliferative field has information 0 on every map. The noise-free profile of an angiogenic switch time on the scalar is wider than the local Cramér–Rao standard deviation.

The scalar is a pattern of one channel, a lag, infrequent times, and a floor. It is not a ctDNA assay. Mode names are row labels on declared flows. They are not marker panels.

This is research only. It is not a medical device, not clinical decision support, not a dose, and not a cure. No document DOI is registered.

See [DISCLAIMER.md](DISCLAIMER.md). The manuscript is [THESIS.md](THESIS.md).

## Files

| Path | Role |
| --- | --- |
| `THESIS.md` | Manuscript (Chapters 1 to 5, Vancouver citations) |
| `THESIS.pdf` | PDF built from the Markdown |
| `build_pdf.py` | Regenerates `THESIS.pdf` |
| `CITATION.cff` | Citation metadata, no document DOI |
| `DISCLAIMER.md` | Research-only boundary |
| `sim/hybrid_observer_toy.py` | Seeded toy maps and classifier (seed 20260921) |
| `sim/results.json` | Numbers cited in Chapter Four |
| `sim/figures/` | Paths, confusion, pairwise error, Fisher summaries, lag, matched burden |

## Reproduce

```bash
python3 -m pip install -r sim/requirements.txt
python3 sim/hybrid_observer_toy.py
python3 build_pdf.py
```

NumPy and Matplotlib are required for the toy. The PDF step also needs the `markdown` and `weasyprint` packages. Regenerating the script rewrites `sim/results.json` and `sim/figures/`.

## Cite

Ogbonna KE. Hybrid occult mode switches under sparse delayed liquid-biopsy-style partial observers [Internet]. Thesis #20 computational research thesis. 21 September 2026 [cited YYYY Mon DD]. Available from: https://github.com/cloudynirvana/thesis-20-occult-modes-partial-liquid-biopsy-observer

Machine-readable fields are in `CITATION.cff`. Add a document DOI there only after one exists.

Hub index, for cataloguing only: [research-theses-hub](https://github.com/cloudynirvana/research-theses-hub).

## Licence

Text and sketch code are MIT, with attribution. Computational research only.
