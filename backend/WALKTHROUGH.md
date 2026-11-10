# Django REST Framework Backend: Comprehensive System Walkthrough

> **Project**: Combinatorics & ML-Guided Exam Seating Allocation System  
> **Backend Path**: `backend/`  
> **Framework**: Django 6.x + Django REST Framework (DRF) + SQLite + CORS Headers

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Project & Directory Layout](#2-project--directory-layout)
3. [Zero-Touch Engine Integration Strategy](#3-zero-touch-engine-integration-strategy)
4. [Database Models & Relational Schema](#4-database-models--relational-schema)
5. [Serializers Layer](#5-serializers-layer)
6. [API Endpoints & Request/Response Reference](#6-api-endpoints--requestresponse-reference)
   - [CRUD Endpoints](#crud-endpoints)
   - [Action Endpoint: Generate Seating](#action-endpoint-generate-seating)
   - [Action Endpoint: Generate Retest (Derangements)](#action-endpoint-generate-retest-derangements)
   - [Action Endpoint: Train & Predict ML Risk](#action-endpoint-train--predict-ml-risk)
   - [Action Endpoint: Seating History by Room](#action-endpoint-seating-history-by-room)
7. [Step-by-Step API Execution Workflow](#7-step-by-step-api-execution-workflow)
8. [Discrete Mathematics & ML Core Connection](#8-discrete-mathematics--ml-core-connection)
9. [Django Admin Portal](#9-django-admin-portal)
10. [Viva & Project Presentation Defense Notes](#10-viva--project-presentation-defense-notes)

---

## 1. Architecture Overview

The backend is built as a **lightweight, clean Django application** without unnecessary microservice overhead. It acts as an API gateway and relational persistence layer over **six standalone mathematical and machine learning engines**:

```
                          +------------------------------------------+
                          |   Frontend / API Client (Vite/React)    |
                          +------------------------------------------+
                                               |
                                        HTTP / JSON REST
                                               v
                          +------------------------------------------+
                          |           Django REST Framework          |
                          |  backend/urls.py -> seating/urls.py     |
                          +------------------------------------------+
                                      |                     |
                                      v                     v
                        +--------------------+    +--------------------+
                        |  ORM & SQLite DB   |    |  API Views &       |
                        |  (Rooms, Students, |    |  Serializers       |
                        |   Constraints,     |    |  (Validation &     |
                        |   SeatingResults)  |    |   Formatting)      |
                        +--------------------+    +--------------------+
                                                        |
                             Calls into internal package|
                                                        v
+---------------------------------------------------------------------------------------------------+
| seating.engines (Zero modifications to mathematical source files)                                  |
|                                                                                                   |
|  - rook_polynomial.py      : Deletion-contraction recursion B = B\e + B/e                         |
|  - inclusion_exclusion.py  : Exact permutation counts: sum((-1)^k * r_k * (n-k)!)                |
|  - derangements.py         : Derangement counts D(n) & random rejection sampling                  |
|  - generating_functions.py : sympy EGF cross-verification D(x) = e^(-x)/(1-x)                     |
|  - seating_board.py        : Classroom grid backtracking solver & retest allocator                |
|  - ml_risk_model.py        : Random Forest classifier for pairwise cheating risk                  |
+---------------------------------------------------------------------------------------------------+
```

### Key Architectural Strengths
1. **Engine Code Immutability**: All original math modules remain untouched. No refactoring was forced on verified combinatorial algorithms.
2. **Layered Constraints**:
   - **Layer 1 (Individual Forbidden Seats)**: Direct mapping to rook polynomial forbidden board cells $(student, seat)$.
   - **Layer 2 (Adjacency / Cheating Conflicts)**: Graph-like spatial avoidance between adjacent seats (horizontal, vertical, diagonal).
   - **Layer 3 (Retest Derangements)**: No student repeats their previous seat from Exam 1 ($D(n)$ constraint).
3. **Stateless Solver, Stateful Storage**: The math solver runs deterministically on input matrices; Django provides audit history, persistence, and CRUD interfaces.

---

## 2. Project & Directory Layout

```
Seating Project/
├── rook_polynomial.py              # Original verified math modules
├── inclusion_exclusion.py
├── derangements.py
├── generating_functions.py
├── seating_board.py
├── ml_risk_model.py
│
└── backend/
    ├── manage.py                   # Django CLI utility
    ├── db.sqlite3                  # SQLite database (auto-generated)
    │
    ├── backend/                    # Project-level configuration
    │   ├── __init__.py
    │   ├── settings.py             # Installed apps, CORS, DRF, SQLite config
    │   ├── urls.py                 # Mounts /api/ and /admin/
    │   ├── wsgi.py
    │   └── asgi.py
    │
    └── seating/                    # Core Django application
        ├── __init__.py
        ├── apps.py                 # AppConfig: 'seating'
        ├── admin.py                # Admin registrations & filters
        ├── models.py               # Room, Student, Constraints, SeatingResult
        ├── serializers.py          # DRF model & action serializers
        ├── views.py                # ViewSets & Action APIViews
        ├── urls.py                 # Route definitions
        ├── migrations/             # Database schema migrations
        │   └── 0001_initial.py
        └── engines/                # Isolated math package
            ├── __init__.py         # sys.path injector for bare-name imports
            ├── rook_polynomial.py
            ├── inclusion_exclusion.py
            ├── derangements.py
            ├── generating_functions.py
            ├── seating_board.py
            └── ml_risk_model.py
```

---

## 3. Zero-Touch Engine Integration Strategy

The standalone math modules rely on bare Python imports (e.g., `from rook_polynomial import rook_polynomial`). In Django packages, subfolder imports typically require relative syntax (`from .rook_polynomial import ...`).

To avoid altering even a single line of mathematical code, `backend/seating/engines/__init__.py` dynamically registers the `engines/` directory into Python's `sys.path`:

```python
# backend/seating/engines/__init__.py
import os
import sys

_engines_dir = os.path.dirname(os.path.abspath(__file__))
if _engines_dir not in sys.path:
    sys.path.insert(0, _engines_dir)
```

Whenever `seating.views` executes:
```python
from seating.engines import seating_board, ml_risk_model
```
`sys.path` is automatically bootstrapped, allowing inter-engine imports like `from derangements import derangement_count_formula` inside `seating_board.py` to resolve seamlessly.

---

## 4. Database Models & Relational Schema

Defined in [`backend/seating/models.py`](file:///c:/Users/pitay/Desktop/Seating%20Project/backend/seating/models.py):

```
+------------------+           +-----------------------------+
|      Room        | 1       * |    ConstraintForbidden      |
+------------------+-----------+-----------------------------+
| id (PK)          |           | id (PK)                     |
| name             |           | room_id (FK -> Room)        |
| rows             |           | student_id (FK -> Student)  |
| cols             |           | seat_index (Integer)        |
+------------------+           +-----------------------------+
         | 1                                 | *
         |                                   |
         | *                                 v
+------------------+ 1         * +-----------------------------+
|  SeatingResult   |   +---------|          Student            |
+------------------+   |         +-----------------------------+
| id (PK)          |   |         | id (PK)                     |
| room_id (FK)     |   |         | name                        |
| generated_at     |   |         | roll_no (Unique: 'S1', etc) |
| assignment (JSON)|   |         +-----------------------------+
| type ('normal' / |   |                     | 1
|       'retest')  |   |                     |
+------------------+   |                     | * (student_a, student_b)
                       |         +-----------------------------+
                       +---------|   ConstraintConflictPair    |
                                 +-----------------------------+
                                 | id (PK)                     |
                                 | room_id (FK -> Room)        |
                                 | student_a (FK -> Student)   |
                                 | student_b (FK -> Student)   |
                                 +-----------------------------+
```

### 1. `Room`
- Physical exam classroom grid.
- Columns: `name` (CharField), `rows` (PositiveInteger), `cols` (PositiveInteger).
- Computed Property: `total_seats = rows * cols`.
- Linear Seat Indexing Formula: $\text{seat\_index} = \text{row} \times \text{cols} + \text{col}$.

### 2. `Student`
- Student identity.
- Columns: `name` (CharField), `roll_no` (CharField, Unique, e.g., `"S1"`, `"CS101"`).
- `roll_no` serves as the invariant key passed to the combinatorics engine.

### 3. `ConstraintForbidden` (Layer 1 Constraint)
- Forbids student $X$ from occupying physical seat index $Y$ in a designated room.
- Direct real-world use case: wheelchair-accessible seats, broken desks, vision impairments.
- Relational link: `ForeignKey(Student)`, `ForeignKey(Room)`, `seat_index`.
- Constraint: `unique_together = ('student', 'room', 'seat_index')`.

### 4. `ConstraintConflictPair` (Layer 2 Constraint)
- Prevents student $A$ and student $B$ from sitting adjacent to each other (Cheating / Disruption avoidance).
- Relational link: `ForeignKey(Student, related_name='conflicts_as_a')`, `ForeignKey(Student, related_name='conflicts_as_b')`, `ForeignKey(Room)`.
- Constraint: `unique_together = ('student_a', 'student_b', 'room')`.

### 5. `SeatingResult`
- Permanent audit log of generated exam arrangements.
- Columns: `room` (FK), `generated_at` (DateTimeField), `type` (`'normal'` or `'retest'`), `assignment` (JSONField).
- `assignment` format: `{"<seat_index>": "<student_roll_no>"}`.
  Example: `{"0": "S1", "2": "S2", "3": "S3"}`.

---

## 5. Serializers Layer

Defined in [`backend/seating/serializers.py`](file:///c:/Users/pitay/Desktop/Seating%20Project/backend/seating/serializers.py):

### Model Serializers (CRUD)
- `RoomSerializer`: Exposes `id`, `name`, `rows`, `cols`, and dynamic read-only `total_seats`.
- `StudentSerializer`: Exposes `id`, `name`, `roll_no`.
- `ConstraintForbiddenSerializer`: Auto-populates readable `student_roll_no` and `room_name` alongside foreign key IDs.
- `ConstraintConflictPairSerializer`: Auto-populates `student_a_roll_no`, `student_b_roll_no`, and `room_name`.
- `SeatingResultSerializer`: Exposes saved seating JSON and timestamp.

### Input Action Serializers (Validation)
- `GenerateSeatingInputSerializer`: Validates that `room_id` exists in DB, accepts boolean `include_diagonal` (default: `True`).
- `GenerateRetestInputSerializer`: Validates that both `room_id` and `previous_result_id` exist in DB, accepts `include_diagonal`.
- `TrainRiskModelInputSerializer`: Validates `room_id`, enforces `threshold` range $[0.0, 1.0]$ (default: `0.75`).

---

## 6. API Endpoints & Request/Response Reference

### Base URL: `http://127.0.0.1:8000/api/`

| HTTP Method | Route | Purpose | Handler View |
|:---|:---|:---|:---|
| `GET / POST` | `/rooms/` | List / Create classrooms | `RoomViewSet` |
| `GET / PUT / DELETE` | `/rooms/<id>/` | Retrieve / Update / Delete classroom | `RoomViewSet` |
| `GET / POST` | `/students/` | List / Register students | `StudentViewSet` |
| `GET / PUT / DELETE` | `/students/<id>/` | Retrieve / Update student | `StudentViewSet` |
| `GET / POST` | `/forbidden-constraints/` | List / Add forbidden seat rules | `ConstraintForbiddenViewSet` |
| `GET / POST` | `/conflict-pairs/` | List / Add student conflict rules | `ConstraintConflictPairViewSet` |
| `POST` | `/generate-seating/` | Compute normal seating plan | `GenerateSeatingView` |
| `POST` | `/generate-retest/` | Compute retest plan with derangement | `GenerateRetestView` |
| `GET` | `/seating-results/<room_id>/` | View all historical plans for a room | `SeatingResultListView` |
| `POST` | `/train-risk-model/` | Train RF model & flag high-risk pairs | `TrainRiskModelView` |

---

### Action Endpoint: Generate Seating
**`POST /api/generate-seating/`**

Pulls the classroom grid, all enrolled students, Layer 1 forbidden seats, and Layer 2 student conflict pairs from the DB, and invokes the MRV backtracking solver.

#### Request Body
```json
{
  "room_id": 1,
  "include_diagonal": true
}
```

#### Success Response (`201 Created`)
```json
{
  "id": 1,
  "room": 1,
  "room_name": "Hall A",
  "generated_at": "2026-09-11T22:15:00.123456Z",
  "assignment": {
    "0": "S1",
    "2": "S2",
    "3": "S3",
    "5": "S4"
  },
  "type": "normal"
}
```

#### Error Response (`409 Conflict`)
```json
{
  "error": "No valid seating arrangement found under the current constraints."
}
```

---

### Action Endpoint: Generate Retest (Derangements)
**`POST /api/generate-retest/`**

Applies the **Derangement constraint**: Reads the seating map from `previous_result_id`, maps each student's previous seat $(student, seat_{old})$ into the forbidden board, and solves for a new seating where:
$$\forall s \in \text{Students}, \quad \text{Seat}_{\text{retest}}(s) \neq \text{Seat}_{\text{exam1}}(s)$$

#### Request Body
```json
{
  "room_id": 1,
  "previous_result_id": 1,
  "include_diagonal": true
}
```

#### Success Response (`201 Created`)
```json
{
  "id": 2,
  "room": 1,
  "room_name": "Hall A",
  "generated_at": "2026-09-11T22:18:22.987654Z",
  "assignment": {
    "1": "S4",
    "2": "S1",
    "4": "S3",
    "5": "S2"
  },
  "type": "retest"
}
```

---

### Action Endpoint: Train & Predict ML Risk
**`POST /api/train-risk-model/`**

Trains a Random Forest classifier on synthetic student feature vectors (`past_incidents_together`, `shared_classes_count`, `academic_similarity_score`), performs inference on all pairs of students in the room, and outputs pairs exceeding the threshold as candidates for Layer 2 conflict constraints.

#### Request Body
```json
{
  "room_id": 1,
  "threshold": 0.75
}
```

#### Success Response (`200 OK`)
```json
{
  "room_id": 1,
  "room_name": "Hall A",
  "threshold": 0.75,
  "total_students": 4,
  "high_risk_pairs": [
    {
      "student_a": "S1",
      "student_b": "S3"
    }
  ],
  "count": 1
}
```

---

## 7. Step-by-Step API Execution Workflow

Here is the exact sequence to run a complete seating simulation via `curl` or Postman:

### 1. Start Development Server
```bash
cd backend
python manage.py runserver
```

### 2. Create a Classroom (2 rows x 3 cols = 6 seats)
```bash
curl -X POST http://127.0.0.1:8000/api/rooms/ \
     -H "Content-Type: application/json" \
     -d '{"name": "Exam Hall 101", "rows": 2, "cols": 3}'
```

### 3. Register Students
```bash
curl -X POST http://127.0.0.1:8000/api/students/ -H "Content-Type: application/json" -d '{"name": "Alice", "roll_no": "S1"}'
curl -X POST http://127.0.0.1:8000/api/students/ -H "Content-Type: application/json" -d '{"name": "Bob", "roll_no": "S2"}'
curl -X POST http://127.0.0.1:8000/api/students/ -H "Content-Type: application/json" -d '{"name": "Charlie", "roll_no": "S3"}'
curl -X POST http://127.0.0.1:8000/api/students/ -H "Content-Type: application/json" -d '{"name": "David", "roll_no": "S4"}'
```

### 4. Add Constraints (Optional)
**Student S1 cannot sit in seat index 0:**
```bash
curl -X POST http://127.0.0.1:8000/api/forbidden-constraints/ \
     -H "Content-Type: application/json" \
     -d '{"student": 1, "room": 1, "seat_index": 0}'
```

**S1 and S2 cannot sit adjacent:**
```bash
curl -X POST http://127.0.0.1:8000/api/conflict-pairs/ \
     -H "Content-Type: application/json" \
     -d '{"student_a": 1, "student_b": 2, "room": 1}'
```

### 5. Generate Normal Seating
```bash
curl -X POST http://127.0.0.1:8000/api/generate-seating/ \
     -H "Content-Type: application/json" \
     -d '{"room_id": 1, "include_diagonal": true}'
```

### 6. Generate Retest (Derangement)
```bash
curl -X POST http://127.0.0.1:8000/api/generate-retest/ \
     -H "Content-Type: application/json" \
     -d '{"room_id": 1, "previous_result_id": 1, "include_diagonal": true}'
```

---

## 8. Discrete Mathematics & ML Core Connection

| Theory / Discrete Math Topic | Underlying Engine | How Django Exposes / Uses It |
|:---|:---|:---|
| **Rook Polynomials** | `rook_polynomial.py` | Computes non-attacking rook configurations on forbidden sub-boards $R(x, B)$ via deletion-contraction recursion $r_k(B) = r_k(B \setminus e) + r_{k-1}(B / e)$. |
| **Principle of Inclusion-Exclusion** | `inclusion_exclusion.py` | Calculates exact number of valid permutations: $N = \sum_{k=0}^{n} (-1)^k r_k (n-k)!$. |
| **Derangements $D(n)$** | `derangements.py` | Subfactorial calculation $!n = \text{round}(n! / e)$ used to mathematically quantify reseating complexity. |
| **Generating Functions** | `generating_functions.py` | Verifies derangement counts via the Exponential Generating Function $D(x) = \frac{e^{-x}}{1-x}$. |
| **Constraint Satisfaction (CSP)** | `seating_board.py` | Backtracking solver with Minimum Remaining Values (MRV) and Forward Checking to assign seats on a 2D grid. |
| **Machine Learning Soft Constraints** | `ml_risk_model.py` | Random Forest predicts cheat/disruption risk $P(\text{risk} \mid \text{features})$; scores $> 0.75$ become hard conflict pairs in the CSP solver. |

---

## 9. Django Admin Portal

All models are registered in [`backend/seating/admin.py`](file:///c:/Users/pitay/Desktop/Seating%20Project/backend/seating/admin.py) with intuitive tabular lists, search fields, and filters:
- Access URL: `http://127.0.0.1:8000/admin/`
- Inspect classrooms, students, active constraints, and JSON assignment trees visually.
- Create a superuser to access:
  ```bash
  python manage.py createsuperuser
  ```

---

## 10. Viva & Project Presentation Defense Notes

### Q1: "Why not use microservices or FastAPI?"
> **Answer**: For an academic examination management system, Django provides built-in ORM security, transaction management, schema migrations, and admin inspection without the operational complexity of distributed services. FastAPI lacks an out-of-the-box admin panel and ORM migration toolchain like Django's.

### Q2: "How did you connect standalone math scripts to Django without breaking them?"
> **Answer**: We maintained complete isolation. The math engine files were placed in `backend/seating/engines/`. The package `__init__.py` injects its absolute directory into `sys.path`. This enables the original bare imports (`from rook_polynomial import ...`) to function identically both as standalone CLI scripts and inside Django requests.

### Q3: "How does the Retest feature enforce derangements with spatial constraints?"
> **Answer**: Pure mathematical derangements $D(n)$ only prevent a student from taking their own previous seat in an abstract permutation. In a real exam hall, we have **both** derangements and spatial adjacency rules. Rather than slow rejection sampling, our backend converts each student's previous seat $(student_i, seat_{\text{old}})$ into an entry on the forbidden board. The backtracking solver then solves both the derangement and adjacency constraints simultaneously in a single CSP search.

### Q4: "Why use ML with Discrete Mathematics?"
> **Answer**: Discrete optimization algorithms excel at **hard constraints** (accessibility, physical walls, forbidden desks). However, determining which students are likely to cheat together is a probabilistic **soft constraint**. The Random Forest model infers pairwise risk from historical behavior; high-probability pairs are dynamically translated into hard constraints for the combinatorics engine.
