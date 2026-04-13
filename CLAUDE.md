# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ASTRA** (Autonomous Scientific & Technological Research Agent) is an AI-driven framework for autonomous cross-domain scientific discovery, hypothesis generation, and validation using real astronomical and socioeconomic data.

The system has two main components:
1. **`astra_live_backend/`** — The active system: a FastAPI server with 89 endpoints, an OODA discovery engine, safety architecture, and self-improvement loop
2. **`astra_core/`** — Legacy cognitive framework (~614 modules, retained for backward compatibility)

### Naming Convention

The system was previously known as "STAN-XI-ASTRO" or "STAN". **It must now be referred to exclusively as "ASTRA"** in all external references, documentation, papers, and user-facing text. Internal code retains `stan_` prefixes for backward compatibility.

**Full name**: ASTRA: Autonomous Scientific & Technological Research Agent

---

## Quick Start

```bash
# Start the backend server
python3 -m astra_live_backend.server
# → http://localhost:8787/

# Run one discovery cycle
curl -X POST http://localhost:8787/api/engine/cycle | python3 -m json.tool

# Run tests
pytest astra_live_backend/ -v
```

---

## Repository Structure

```
ASTRA/
├── astra_live_backend/          ← Active system (89 endpoints, 33 modules)
│   ├── server.py                   FastAPI app & routes
│   ├── engine.py                   OODA discovery cycle
│   ├── hypotheses.py               Hypothesis state machine
│   ├── statistics.py               Statistical tests, FDR, effect sizes
│   ├── data_registry.py            9 data source registry
│   ├── safety/                     Safety subsystem (12 modules)
│   ├── sprints/                    Domain-specific research sprints
│   └── test_*.py                   Test suites (58+ tests)
│
├── paper/                       ← RASTI paper (MNRAS format)
│   ├── astra-rasti-v2.tex          Main manuscript
│   ├── supplement.tex              Supplementary material
│   ├── references-v2.bib           Bibliography
│   ├── figures/                    6 publication figures + generator
│   ├── mnras.cls, mnras.bst        MNRAS LaTeX class & style
│   └── generate_supplement.py      Auto-generate supplement from API
│
├── astra_core/                   ← Legacy cognitive framework (~614 modules)
├── self_evolution/              ← Self-improvement engine
├── pipeline/                    ← Per-hypothesis analysis scripts
├── config/                      ← System prompts & configuration
├── knowledge/                   ← Accumulated findings
├── hypotheses/                  ← Hypothesis queue & graveyard
├── logs/                        ← Run logs
└── reproduce.py                 ← Reproducibility verification tool
```

---

## Active System: astra_live_backend/

### Key Modules

| Module | Purpose |
|--------|---------|
| `server.py` | FastAPI application, 89 route definitions |
| `engine.py` | OODA cycle orchestrator (Orient→Select→Investigate→Evaluate→Update) |
| `hypotheses.py` | Hypothesis lifecycle, phase gates, confidence tracking |
| `statistics.py` | KS, χ², t-test, Pearson, Granger + FDR correction, effect sizes |
| `cosmology.py` | ΛCDM distance modulus, H₀ fitting, Laplace uncertainty |
| `data_registry.py` | Registry pattern for 9 astronomical/socioeconomic data sources |
| `data_fetcher.py` | Fetch & cache real data from APIs |
| `bayesian.py` | BIC model comparison, Bayes factors, Laplace posteriors |
| `causal.py` | PC/FCI causal algorithms, do-calculus interventions |
| `literature.py` | TF-IDF similarity, arXiv integration, novelty scoring |
| `discovery_memory.py` | SQLite memory of all discoveries & method outcomes |
| `hypothesis_generator.py` | Auto-generate hypotheses from discovery patterns |
| `adaptive_strategist.py` | Epsilon-greedy method selection by domain |
| `paper_generator.py` | Auto-draft LaTeX from validated hypotheses |
| `degradation.py` | Long-run health monitoring |
| `exporter.py` | JSON/CSV/LaTeX/report export |
| `provenance.py` | Discovery lineage tracking |

### Safety Subsystem (`safety/`)

| Module | Purpose |
|--------|---------|
| `controller.py` | 5-state FSM: BOOT→NOMINAL→DEGRADED→SAFE_MODE→EMERGENCY_STOP |
| `arbiter.py` | Reviews engine decisions, issues verdicts, supports overrides |
| `circuit_breakers.py` | Automatic fault isolation (error rate, anomaly, resource) |
| `supervisor.py` | Shift-based human oversight with action logging |
| `ceremony.py` | Formal state transition protocol |
| `ethics.py` | Ethics reasoning engine |
| `phased_autonomy.py` | Graduated autonomy levels |
| `orp.py` | Operational Readiness Protocol |
| `safety_case.py` | Structured hazard/claim/risk registry |
| `health.py` | System health checks |
| `audit.py` | Immutable audit trail |

### Data Sources (9 total, 27,430+ data points)

Pantheon+ SNe Ia (1,701) · NASA Exoplanet Archive (2,839) · Gaia DR3 (4,984) · SDSS DR18 (2,000+) · LIGO GW (280) · Planck CMB (2,507) · ZTF Transients (2,000) · TESS · SDSS Clusters

---

## Development Workflow

### Running the Server

```bash
python3 -m astra_live_backend.server
# Serves on http://localhost:8787/
```

### Tests

```bash
pytest astra_live_backend/ -v                    # All backend tests
pytest astra_live_backend/test_phase10.py -v     # Long-run stability
pytest astra_live_backend/test_phase11.py -v     # Publication & export
```

### Dashboard

The live dashboard is generated from an HTML template with an injected JSON snapshot:

```bash
# Edit CSS/JS in the HTML template (edits persist through regeneration)
# Then regenerate with latest data:
python3 astra_live_backend/generate_dashboard.py
```

### Paper & Figures

```bash
cd paper

# Generate all 6 figures
python3 figures/generate_figures.py

# Compile paper
pdflatex astra-rasti-v2.tex && bibtex astra-rasti-v2 && pdflatex astra-rasti-v2.tex && pdflatex astra-rasti-v2.tex
```

### Reproducibility

```bash
python3 reproduce.py --list              # List reproducible discoveries
python3 reproduce.py <discovery_id>      # Reproduce one
python3 reproduce.py --all               # Reproduce all
```

---

## Legacy System: astra_core/

The `astra_core/` directory contains the original cognitive framework (~614 Python modules, ~280K LoC). It includes domain modules, physics engines, reasoning capabilities, and memory systems. **This code is retained for backward compatibility but is not actively developed.** The active system is `astra_live_backend/`.

Internal module names still use `stan_` prefixes — this is intentional and should not be renamed.

### Key Legacy Patterns

- **Factory functions**: Use `create_<module>()`, not direct constructors
- **Graceful degradation**: All imports wrapped in try/except with fallback
- **Domain hot-swapping**: Modules inherit from `BaseDomainModule` with standardized interface
- **Physics constants**: Always use `UnifiedPhysicsEngine.constants` (CGS units)

---

## Important Notes

1. **External naming**: Always use "ASTRA" in papers, docs, and user-facing text
2. **Data files**: `.csv`, `.fits`, `.hdf5` are gitignored — data is fetched live from APIs
3. **PDFs**: Paper PDFs and figures are gitignored — regenerate from LaTeX source
4. **Discovery database**: SQLite WAL at runtime location (not in repo)
5. **Dashboard HTML**: Static file served publicly — always regenerate after changes
