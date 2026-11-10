# Derange

A combinatorics-driven exam-hall seating allocator, built as a Discrete
Mathematics project. It uses **rook polynomials**, the **inclusion-exclusion
principle**, and **derangements** — cross-verified against a fourth method,
**generating functions** — to compute and generate conflict-free seating
arrangements, wrapped in a full-stack app with a constraint-satisfaction
solver and a transparently-labeled ML risk-scoring layer.

---

## Why this project

Most seating-chart tools are either manual spreadsheets or simple random
shufflers. This project instead treats seating as what it actually is: a
constrained permutation problem, and applies the right tool for each type of
constraint that shows up in a real exam hall.

## The math core

| Concept | Role in this project |
|---|---|
| **Rook polynomials** | Deletion-contraction recursion computes the coefficients of a forbidden-position board — how many ways to place *k* non-attacking "rooks" (student-seat conflicts). |
| **Inclusion-exclusion** | Plugs those coefficients into the classic forbidden-positions formula `Σ (-1)^k · r_k · (n-k)!` to get an **exact** count of valid seatings, avoiding all individually-forbidden (student, seat) pairs. |
| **Derangements** | The special case where every student is forbidden from their *own* previous seat — used for retest re-seating, where nobody can repeat their old seat. |
| **Generating functions** | Independently verifies the derangement counts using the EGF `D(x) = e^(-x)/(1-x)`, cross-checked via `sympy` series expansion against the recurrence and the rook-polynomial/inclusion-exclusion result. |

All three counting methods (recurrence, rook+I-E, generating function) agree
exactly for every tested value of *n* — see `backend/seating/engines/`.

## Two constraint types, two different tools

A real exam hall has two fundamentally different kinds of constraints, and
they can't both be solved the same way:

- **Individual forbidden seats** ("Student X can't sit in seat Y") — a fixed,
  one-to-one constraint. Solved **analytically** and exactly via rook
  polynomials + inclusion-exclusion. No search required.
- **Pairwise adjacency conflicts** ("Students A and B can't sit near each
  other") — a *relational* constraint between two positions, which cannot be
  expressed as a single forbidden (item, position) cell. Rook polynomials
  don't cover this. Solved instead with a **backtracking CSP solver**,
  validated against brute-force enumeration on small rooms to prove
  correctness.

This separation is deliberate — it reflects where the classical combinatorics
formula actually applies, and where a search algorithm is genuinely needed.

## ML risk-scoring layer (with honest data provenance)

A Random Forest classifier flags potentially high-risk student pairs, but the
project is explicit about **where each feature's data actually comes from**:

| Feature | Source |
|---|---|
| `roll_number_proximity` | **Real** — computed directly from an anonymized class roster CSV (real USN structure, no fabricated data). |
| `past_incidents_together` | Simulated by default, since no real incident data exists — unless real evidence is manually supplied for a specific pair. |
| `academic_similarity_score` | Same as above. |
| `shared_classes_count` | Always simulated in this dataset (every student shares an identical subject list, so this feature has no real signal here). |

The system tracks provenance **per feature, per pair** and reports one of
three states — `real`, `partial`, or `simulated` — rather than a single
blanket flag. The frontend surfaces this directly via a **Feature Provenance
Matrix** and color-coded honesty banners, so no prediction is ever presented
as more "real" than it actually is.

A `PROTECTED_REAL_NAMES` safeguard also ensures that no real (non-anonymized)
student name can ever appear in a "high-risk" flagged output, regardless of
the underlying score.

## Architecture

```
Derange/
├── .gitignore
├── package.json               # Root dev runner script (concurrently)
├── README.md
├── backend/                   # Django + Django REST Framework
│   ├── .env.example
│   ├── requirements.txt       # Backend dependencies pinned
│   ├── pytest.ini
│   ├── manage.py
│   ├── backend/               # Project configuration (settings, urls, wsgi, asgi)
│   └── seating/
│       ├── engines/           # Standalone math/ML modules (importable & testable alone)
│       │   ├── rook_polynomial.py
│       │   ├── inclusion_exclusion.py
│       │   ├── derangements.py
│       │   ├── generating_functions.py
│       │   ├── seating_board.py      # Backtracking CSP solver + retest re-seating
│       │   └── ml_risk_model.py      # Random Forest + provenance tracking
│       ├── data/               # students_anonymized.csv (real roster structure, anonymized)
│       ├── models.py / views.py / serializers.py / urls.py
│       └── tests/             # Unit tests for combinatorial & seating engines
└── frontend/                  # React + Vite + Tailwind CSS
    ├── .env.example
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── tabs/              # Setup, Constraints, Generate & Results, Risk Model (ML)
        ├── components/        # SeatingGrid, Navbar, Alert, MathExplainerPanel
        ├── context/           # RoomContext (active room state)
        └── api/client.js      # Axios client for the Django REST API
```

## Tech stack

- **Math/ML engine:** Python, `sympy`, `numpy`, `pandas`, `scikit-learn`
- **Backend:** Django, Django REST Framework, SQLite (dev)
- **Frontend:** React, Vite, Tailwind CSS v4, Chart.js (`react-chartjs-2`), React Router
- **Planned:** Docker, Kubernetes (for portfolio-stage deployment)

## Environment Variables

### Backend (`backend/.env` — see `backend/.env.example`)

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Django secret key | Current dev key |
| `DJANGO_DEBUG` | Enable debug mode (`1` for True, `0` for False) | `1` (True) |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hostnames | `localhost,127.0.0.1` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed CORS origins | `http://localhost:5173,http://127.0.0.1:5173` |
| `DJANGO_DB_PATH` | Path to the SQLite database file | `BASE_DIR / 'db.sqlite3'` |

### Frontend (`frontend/.env` — see `frontend/.env.example`)

| Variable | Description | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Base URL for the Django REST API | `http://127.0.0.1:8000/api` |

## Setup & Running Locally

### 1. Install Dependencies

**Backend:**
```bash
pip install -r backend/requirements.txt
```

**Frontend:**
```bash
cd frontend && npm install && cd ..
```

**Root orchestration:**
```bash
npm install
```

### 2. Database Migrations

```bash
cd backend
python manage.py migrate
cd ..
```

### 3. Run the Full Stack

Start both the Django backend (`http://127.0.0.1:8000`) and the React+Vite frontend (`http://localhost:5173`) with a single command from the root directory:

```bash
npm run dev
```

Alternatively, you can run each service independently:
- **Backend:** `python backend/manage.py runserver`
- **Frontend:** `npm --prefix frontend run dev`

### 4. Running Backend Tests

```bash
cd backend
python -m pytest -v
```

## Key API endpoints

| Endpoint | Purpose |
|---|---|
| `GET, POST /api/rooms/` | List and create exam rooms |
| `GET, POST, PATCH, DELETE /api/students/` | Manage student roster |
| `GET, POST, DELETE /api/conflict-pairs/` | Manage pairwise adjacency conflicts |
| `GET, POST, DELETE /api/forbidden-constraints/` | Manage forbidden seat constraints |
| `POST /api/generate-seating/` | Generate a conflict-free seating chart for a room |
| `POST /api/generate-retest/` | Generate a retest seating (derangement of the previous arrangement) |
| `POST /api/train-risk-model/` | Train and score the ML risk model, with optional real roster/evidence input |
| `GET /api/seating-results/<room_id>/` | Retrieve past seating results for a room |
| `GET /api/math-explainer/<room_id>/` | Analytical breakdown (rook poly + I-E coefficients) |

## Data & privacy notes

The class roster used for real structural features is **anonymized**
(`students_anonymized.csv`) — real names/USNs were replaced with generic IDs
before use, except for a small number of names the author chose to keep
personally, with an explicit runtime safeguard (`PROTECTED_REAL_NAMES`)
preventing any of those names from ever appearing in a flagged ML output.

## Status

Core math engine, backend API, frontend UI, and ML provenance system are
functional and tested end-to-end. Docker and Kubernetes deployment are
planned as a post-submission extension.

---

*Built as a Discrete Mathematics course project (Modules I–III: Inclusion-
Exclusion, Derangements, Rook Polynomials, Generating Functions), extended
with a full-stack implementation and applied ML for portfolio purposes.*
