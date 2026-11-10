"""
ml_risk_model.py
-----------------
Machine-learning "soft constraint" generator for the seating system.

PURPOSE:
    The backtracking solver in seating_board.py handles HARD constraints
    (individual forbidden pairs, adjacency conflicts).  But in a real
    classroom, deciding WHICH student pairs to flag as "conflict pairs" is
    itself a judgement call.  This module automates that judgement by
    training a Random Forest classifier on historical/synthetic student-pair
    data, then using the trained model to predict which pairs are high-risk
    for cheating or disruption.

    The output — a list of (student_A, student_B) tuples — plugs directly
    into seating_board.py's `conflict_pairs` parameter.

FEATURES (4-Feature Architecture):
    1. past_incidents_together: Count of prior disciplinary/cheating flags (0, 1, 2+).
    2. shared_classes_count: Number of shared course enrollments (0-5).
    3. academic_similarity_score: Cosine similarity of academic performance (0.0-1.0).
    4. roll_number_proximity: Proximity based on institutional USN/Roll sequence (0.0-1.0).
       Computed for REAL when roster_csv_path is provided as:
           1.0 - (abs(usn_num_a - usn_num_b) / max_usn_gap_in_class)

PIPELINE OVERVIEW:
    1. load_roster()              — loads real student USN + Name from CSV
    2. compute_roll_proximity()   — computes normalized roll proximity score
    3. generate_simulated_data()  — synthetic training data with all 4 features
    4. train_risk_model()         — Random Forest + evaluation metrics
    5. get_high_risk_pairs()      — inference on live student roster with real
                                    roster proximity & privacy safeguards
"""

import os
import re
import csv
import logging
import warnings
from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report

logger = logging.getLogger(__name__)

# =======================================================================
#  REAL-NAME PRIVACY SAFEGUARD
# =======================================================================
# Any student whose name matches an entry in this set will be filtered OUT
# of high-risk conflict predictions to protect personal privacy and ensure
# non-anonymized students are never publicly flagged in disciplinary outputs.
PROTECTED_REAL_NAMES = set()

def _load_protected_real_names():
    """
    Populate PROTECTED_REAL_NAMES at import time from, in this order:
      (a) seating/data/protected_names.local.txt if it exists
      (b) comma-separated env var PROTECTED_REAL_NAMES if set
    Uses the same normalization (strip whitespace, uppercase) as the exclusion filter.
    If neither exists, the set stays empty.
    """
    names = set()
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_path = os.path.join(app_dir, 'data', 'protected_names.local.txt')
    if os.path.isfile(local_path):
        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                for line in f:
                    c = line.strip()
                    if c and not c.startswith('#'):
                        names.add(c)
                        names.add(c.upper())
        except Exception as exc:
            logger.warning(f"Failed to read protected_names.local.txt: {exc}")
    elif 'PROTECTED_REAL_NAMES' in os.environ:
        raw_env = os.environ.get('PROTECTED_REAL_NAMES', '')
        for part in raw_env.split(','):
            c = part.strip()
            if c:
                names.add(c)
                names.add(c.upper())
    return names

PROTECTED_REAL_NAMES.update(_load_protected_real_names())


# =======================================================================
#  CUSTOM EXCEPTIONS
# =======================================================================

class RosterMismatchError(Exception):
    """
    Raised when one or more student identifiers in student_list do not match
    any USN in the real roster CSV during roll_number_proximity evaluation.
    """
    def __init__(self, unmatched_ids, message=None):
        self.unmatched_ids = list(unmatched_ids)
        if message is None:
            message = (
                f"The following student IDs do not match any USN in the roster CSV "
                f"and cannot have a real roll_number_proximity computed: {self.unmatched_ids}. "
                f"Either fix these roll_no values to match real USNs, or omit "
                f"use_real_roster to fall back to simulated proximity."
            )
        super().__init__(message)


# =======================================================================
#  0. ROSTER DATA LOADER & PROXIMITY ENGINE
# =======================================================================

class Roster(dict):
    """
    Dictionary mapping USN -> Student Name, augmented with parsed
    numeric suffixes and class-wide max gap for roll proximity calculation.
    """
    def __init__(self, mapping=None, usn_numbers=None, min_usn=0, max_usn=0):
        super().__init__(mapping or {})
        self.usn_numbers = usn_numbers or {}  # usn_str -> int
        self.min_usn = min_usn
        self.max_usn = max_usn
        self.max_gap = max(1, max_usn - min_usn)


class RiskPairs(list):
    """
    List subclass for returning high-risk pairs while retaining
    metadata about feature provenance (feature_sources) and the count
    of pairs that had manually-entered real evidence.
    """
    def __init__(self, iterable=None, feature_sources=None, pairs_with_real_evidence=0):
        super().__init__(iterable or [])
        self.feature_sources = feature_sources or {}
        self.pairs_with_real_evidence = pairs_with_real_evidence


def validate_roster_membership(student_list, roster):
    """
    Check every student ID in student_list against the roster's USN keys.

    Parameters
    ----------
    student_list : iterable of str
        List of student IDs / roll numbers to validate.
    roster : Roster or dict
        Loaded roster dictionary from load_roster().

    Returns
    -------
    tuple of (list, list)
        (matched, unmatched) lists of student IDs.
    """
    if hasattr(roster, 'usn_numbers') and roster.usn_numbers:
        valid_keys = set(roster.usn_numbers.keys())
    elif hasattr(roster, 'keys'):
        valid_keys = set(roster.keys())
    else:
        valid_keys = set()

    matched = []
    unmatched = []
    for sid in student_list:
        if sid in valid_keys:
            matched.append(sid)
        else:
            unmatched.append(sid)

    return matched, unmatched


def _extract_usn_number(usn_str):
    """
    Extract trailing integer from a USN string (e.g., 'STU0005' -> 5, 'S12' -> 12).
    Returns None if no numeric suffix can be parsed.
    """
    if not usn_str or not isinstance(usn_str, str):
        return None
    match = re.search(r'(\d+)$', usn_str.strip())
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def get_default_roster_path():
    """
    Returns the preferred roster path:
    Prefers seating/data/students_roster.local.csv when it exists,
    falling back to students_anonymized.csv otherwise.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(os.path.dirname(current_dir), 'data')
    local_path = os.path.join(data_dir, 'students_roster.local.csv')
    fallback_path = os.path.join(data_dir, 'students_anonymized.csv')
    return local_path if os.path.exists(local_path) else fallback_path


def load_roster(csv_path=None):
    """
    Read the student roster CSV containing USN and Name columns.
    Prefers students_roster.local.csv if it exists and falls back to students_anonymized.csv.

    Parameters
    ----------
    csv_path : str, optional
        Path to the CSV file (must have 'USN' and 'Name' columns).
        Defaults to get_default_roster_path().

    Returns
    -------
    Roster (dict-like)
        Mapping from USN -> Name, with attributes .usn_numbers and .max_gap.
    """
    if csv_path is None:
        csv_path = get_default_roster_path()
    elif os.path.basename(csv_path) == 'students_anonymized.csv':
        local_candidate = os.path.join(os.path.dirname(csv_path), 'students_roster.local.csv')
        if os.path.exists(local_candidate):
            csv_path = local_candidate

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Roster CSV file not found at: {csv_path}")

    mapping = {}
    usn_numbers = {}

    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            usn = row.get("USN", "").strip()
            name = row.get("Name", "").strip()
            if not usn:
                continue
            mapping[usn] = name
            num = _extract_usn_number(usn)
            if num is not None:
                usn_numbers[usn] = num
            else:
                logger.warning(f"Could not parse trailing numeric suffix from USN '{usn}' in roster.")

    if usn_numbers:
        min_num = min(usn_numbers.values())
        max_num = max(usn_numbers.values())
    else:
        min_num, max_num = 0, 1

    return Roster(mapping=mapping, usn_numbers=usn_numbers, min_usn=min_num, max_usn=max_num)


def compute_roll_proximity(usn_a, usn_b, roster):
    """
    Extract the trailing numeric part of each USN and return the normalized
    proximity score:
        1.0 - (abs(usn_num_a - usn_num_b) / max_usn_gap_in_class)

    Scores:
        0.0 = furthest apart in the class.
        1.0 = adjacent roll numbers (or identical).

    Parameters
    ----------
    usn_a : str
        USN / identifier for student A (must exist in roster).
    usn_b : str
        USN / identifier for student B (must exist in roster).
    roster : Roster or dict
        Roster object loaded via load_roster().

    Returns
    -------
    float or None
        Normalized proximity score in [0.0, 1.0], or None if unparseable or not in roster.
    """
    num_a = None
    if hasattr(roster, 'usn_numbers') and usn_a in roster.usn_numbers:
        num_a = roster.usn_numbers[usn_a]
    elif hasattr(roster, '__contains__') and usn_a in roster:
        num_a = _extract_usn_number(usn_a)
    else:
        num_a = None

    num_b = None
    if hasattr(roster, 'usn_numbers') and usn_b in roster.usn_numbers:
        num_b = roster.usn_numbers[usn_b]
    elif hasattr(roster, '__contains__') and usn_b in roster:
        num_b = _extract_usn_number(usn_b)
    else:
        num_b = None

    if num_a is None:
        logger.warning(f"Failed to resolve USN A '{usn_a}' in roster. Skipping roll proximity calculation.")
        return None
    if num_b is None:
        logger.warning(f"Failed to resolve USN B '{usn_b}' in roster. Skipping roll proximity calculation.")
        return None

    if hasattr(roster, 'max_gap') and roster.max_gap > 0:
        max_gap = roster.max_gap
    else:
        max_gap = 1

    gap = abs(num_a - num_b)
    score = 1.0 - (gap / max_gap)
    return round(max(0.0, min(1.0, score)), 4)


# =======================================================================
#  1. DATA SIMULATION
# =======================================================================

def generate_simulated_data(num_pairs=1000, random_state=42):
    """
    Create a synthetic dataset of student pairs with features that
    plausibly predict cheating/disruption risk across 4 feature dimensions.

    FEATURES:
        - past_incidents_together:  Number of prior incidents (0, 1, 2+).
        - shared_classes_count:     How many classes they share (0-5).
        - academic_similarity_score: Cosine-style similarity of grades (0.0 to 1.0).
        - roll_number_proximity:    Institutional USN proximity (0.0 to 1.0).

    TARGET (conflict_risk_label):
        Binary. Generated via logistic-style weighted rule:
            risk_score = 0.45 * (past_incidents / 3.0)
                       + 0.15 * (shared_classes / 5.0)
                       + 0.25 * academic_similarity
                       + 0.15 * roll_number_proximity

        WHY this rule?  We want the model to learn a realistic decision
        boundary where past_incidents dominates (45% weight), academic
        similarity matters (25%), shared classes provide supporting
        evidence (15%), and roll proximity accounts for seating/lab
        affinity (15%).  Weights sum to exactly 1.00.

    Parameters
    ----------
    num_pairs : int
        Number of student-pair samples to generate.
    random_state : int
        Seed for reproducibility (critical for CI/CD pipelines).

    Returns
    -------
    pd.DataFrame
        Columns: student_a_id, student_b_id, past_incidents_together,
                 shared_classes_count, academic_similarity_score,
                 roll_number_proximity, conflict_risk_label
    """
    rng = np.random.RandomState(random_state)

    # -- Generate student IDs -------------------------------------------------
    student_a_ids = [f"STU_{i:04d}_A" for i in range(num_pairs)]
    student_b_ids = [f"STU_{i:04d}_B" for i in range(num_pairs)]

    # -- Feature 1: past incidents (right-skewed, most pairs have 0) ----------
    past_incidents = rng.choice(
        [0, 1, 2, 3],
        size=num_pairs,
        p=[0.60, 0.25, 0.10, 0.05]
    )

    # -- Feature 2: shared classes (uniform 0-5) ------------------------------
    shared_classes = rng.randint(0, 6, size=num_pairs)

    # -- Feature 3: academic similarity (beta distribution, centered ~0.5) ----
    academic_similarity = rng.beta(2, 2, size=num_pairs)

    # -- Feature 4: roll number proximity (uniform 0.0 to 1.0) ----------------
    # NOTE: Even though we compute this feature for REAL for inference later,
    # the TRAINING set still needs synthetic examples across the full range of
    # values so the model learns the relationship.
    roll_proximity = rng.uniform(0.0, 1.0, size=num_pairs)

    # -- Target: deterministic rule + noise -----------------------------------
    # Rebalanced weights summing to 1.00:
    # 0.45 (past incidents) + 0.15 (shared classes) + 0.25 (academic sim) + 0.15 (roll proximity)
    risk_score = (
        0.45 * (past_incidents / 3.0) +
        0.15 * (shared_classes / 5.0) +
        0.25 * academic_similarity +
        0.15 * roll_proximity
    )

    noise = rng.normal(0, 0.05, size=num_pairs)
    risk_score_noisy = risk_score + noise

    # Threshold to create binary labels (~30-35% positive rate)
    conflict_risk_label = (risk_score_noisy > 0.45).astype(int)

    df = pd.DataFrame({
        "student_a_id": student_a_ids,
        "student_b_id": student_b_ids,
        "past_incidents_together": past_incidents,
        "shared_classes_count": shared_classes,
        "academic_similarity_score": np.round(academic_similarity, 4),
        "roll_number_proximity": np.round(roll_proximity, 4),
        "conflict_risk_label": conflict_risk_label,
    })

    return df


# =======================================================================
#  2. MODEL TRAINING
# =======================================================================

def train_risk_model(df, test_size=0.2, random_state=42):
    """
    Train a Random Forest classifier to predict conflict_risk_label
    from the 4 numeric features.

    Parameters
    ----------
    df : pd.DataFrame
        Output of generate_simulated_data().
    test_size : float
        Fraction of data to hold out for evaluation.
    random_state : int
        Seed for reproducible train/test splits and model training.

    Returns
    -------
    sklearn.ensemble.RandomForestClassifier
        The trained model, ready for inference via predict_proba().
    """
    feature_cols = [
        "past_incidents_together",
        "shared_classes_count",
        "academic_similarity_score",
        "roll_number_proximity",
    ]
    X = df[feature_cols]
    y = df["conflict_risk_label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
    )

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=None,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\n--- Random Forest Classification Report ---")
    print(f"    Train size: {len(X_train)}, Test size: {len(X_test)}")
    print(classification_report(
        y_test, y_pred,
        target_names=["Safe (0)", "High Risk (1)"],
    ))

    importances = model.feature_importances_
    print("  Feature Importances:")
    for feat, imp in sorted(zip(feature_cols, importances),
                            key=lambda x: -x[1]):
        bar = "#" * int(imp * 40)
        print(f"    {feat:>30s}: {imp:.3f}  {bar}")
    print()

    return model


# =======================================================================
#  3. INFERENCE & INTEGRATION
# =======================================================================

def get_high_risk_pairs(model, student_list, threshold=0.75, student_features=None, roster_csv_path=None, strict_roster_check=True):
    """
    Score every unique pair from `student_list` and return those whose
    predicted conflict probability exceeds `threshold`.

    ===========================================================================
    FEATURE TRANSPARENCY & DATA PROVENANCE:
    ---------------------------------------
    - roll_number_proximity:
      When `roster_csv_path` is provided, this feature is computed from REAL
      student USNs in the roster CSV.
      If `roster_csv_path` is omitted, it falls back to simulated/neutral values.

    - past_incidents_together & academic_similarity_score:
      Derived from `student_features` if provided; otherwise falls back to
      neutral baseline values (0 incidents, 0 shared classes, 0.5 similarity).
    ===========================================================================

    ROSTER VALIDATION & STRICTNESS (strict_roster_check):
    -----------------------------------------------------
    - When strict_roster_check=True (default), any student ID in student_list that
      does not match a genuine USN in the roster CSV immediately raises
      RosterMismatchError.
    - When strict_roster_check=False, a warning is logged and pairs involving
      unmatched student IDs fall back to a neutral proximity baseline (0.5),
      while pairs where both students exist in the roster still receive their
      genuine, real roll_number_proximity score.

    PRIVACY SAFEGUARD:
    ------------------
    Any student whose name appears in `PROTECTED_REAL_NAMES` is excluded from
    high-risk outputs, preventing real, non-anonymized students from being flagged.

    Parameters
    ----------
    model : RandomForestClassifier
        Trained model from train_risk_model().
    student_list : list of str
        Student identifiers (e.g. ["STU0005", "STU0006", ...]).
    threshold : float
        Probability cutoff. Pairs with P(conflict) >= threshold are flagged.
    student_features : dict, optional
        Mapping of student pairs to feature dicts, keyed by frozenset({student_a, student_b}).
    roster_csv_path : str, optional
        Path to students_anonymized.csv for computing REAL roll proximity.
    strict_roster_check : bool, optional
        If True (default), raises RosterMismatchError if any student_list ID is
        missing from the roster. If False, logs a warning and uses 0.5 for unmatched pairs.

    Returns
    -------
    list of tuple
        Each tuple is (student_A, student_B) for a high-risk pair.
        The list object also includes a `.feature_sources` attribute reporting
        whether each feature was 'real' or 'simulated'.
    """
    all_pairs = list(combinations(student_list, 2))
    if not all_pairs:
        return RiskPairs([], feature_sources={
            "roll_number_proximity": "real" if roster_csv_path else "simulated",
            "past_incidents_together": "simulated",
            "shared_classes_count": "simulated",
            "academic_similarity_score": "simulated",
        }, pairs_with_real_evidence=0)

    # 1. Load real roster if CSV path provided
    roster = None
    unmatched_ids = []
    if roster_csv_path:
        try:
            roster = load_roster(roster_csv_path)
            logger.info(f"Loaded roster with {len(roster)} students from {roster_csv_path}.")
        except Exception as e:
            logger.error(f"Failed to load roster from {roster_csv_path}: {e}")
            warnings.warn(f"Failed to load roster from {roster_csv_path}: {e}", UserWarning, stacklevel=2)

        if roster:
            matched_ids, unmatched_ids = validate_roster_membership(student_list, roster)
            if unmatched_ids:
                if strict_roster_check:
                    raise RosterMismatchError(unmatched_ids)
                else:
                    msg = (
                        f"The following student IDs do not match any USN in the roster CSV and "
                        f"cannot have a real roll_number_proximity computed: {unmatched_ids}. "
                        f"strict_roster_check is False: falling back to neutral proximity (0.5) "
                        f"for pairs involving these students, while computing real proximity for matched pairs."
                    )
                    warnings.warn(msg, UserWarning, stacklevel=2)
                    logger.warning(msg)
                    print(f"[ml_risk_model WARNING] {msg}")

    # 2. Compute per-field provenance across actual pairs
    #    Each evidence-eligible field is checked per-pair: does this specific
    #    key literally exist in the pair's student_features entry?
    evidence_fields = ["past_incidents_together", "shared_classes_count", "academic_similarity_score"]
    total_pairs = len(all_pairs)
    pairs_with_real_evidence = 0

    if student_features is not None:
        # Count how many of the actual pairs have an entry in student_features,
        # and per-field how many pairs have that specific key present.
        field_real_counts = {f: 0 for f in evidence_fields}
        for s_a, s_b in all_pairs:
            pair_key = frozenset({s_a, s_b})
            pair_data = student_features.get(pair_key)
            if pair_data is None:
                pair_data = student_features.get((s_a, s_b), student_features.get((s_b, s_a)))
            if pair_data is not None:
                pairs_with_real_evidence += 1
                for field in evidence_fields:
                    if field in pair_data:
                        field_real_counts[field] += 1

        def _provenance_label(count, total):
            if count == 0:
                return "simulated"
            elif count == total:
                return "real"
            else:
                return "partial"

        feature_sources = {
            "roll_number_proximity": "real" if roster else "simulated",
        }
        for field in evidence_fields:
            feature_sources[field] = _provenance_label(field_real_counts[field], total_pairs)

        # Attach per-field counts for the frontend's partial badge (N/M)
        feature_sources["_field_counts"] = {
            field: {"real": field_real_counts[field], "total": total_pairs}
            for field in evidence_fields
        }
    else:
        feature_sources = {
            "roll_number_proximity": "real" if roster else "simulated",
            "past_incidents_together": "simulated",
            "shared_classes_count": "simulated",
            "academic_similarity_score": "simulated",
        }

    if roster:
        if student_features is None:
            msg = (
                f"student_features not provided for incident/grade metrics (using neutral baselines/simulated), "
                f"but roll_number_proximity IS computed from REAL roster data at '{roster_csv_path}'."
            )
            warnings.warn(msg, UserWarning, stacklevel=2)
            logger.info(msg)
            print(f"[ml_risk_model INFO] {msg}")
    else:
        if student_features is None:
            msg = (
                "student_features was not provided to get_high_risk_pairs(). "
                "Falling back to randomly simulated feature vectors. "
                "WARNING: Output high-risk pairs are NOT based on real student data!"
            )
            warnings.warn(msg, UserWarning, stacklevel=2)
            logger.warning(msg)
            print(f"[ml_risk_model WARNING] {msg}")

    # 3. Assemble feature rows for inference
    feature_rows = []
    valid_pairs = []

    rng = np.random.RandomState(123)

    for s_a, s_b in all_pairs:
        # Resolve roll number proximity
        if roster:
            if s_a in roster and s_b in roster:
                prox = compute_roll_proximity(s_a, s_b, roster)
                if prox is None:
                    logger.warning(f"Could not compute roll proximity for pair ({s_a}, {s_b}); using 0.5 baseline.")
                    prox = 0.5
            else:
                # strict_roster_check is False: neutral baseline (0.5) for pairs involving unmatched IDs
                prox = 0.5
        elif student_features and frozenset({s_a, s_b}) in student_features:
            prox = float(student_features[frozenset({s_a, s_b})].get("roll_number_proximity", 0.5))
        else:
            prox = float(rng.uniform(0.0, 1.0))

        # Resolve other three features
        if student_features is not None:
            pair_key = frozenset({s_a, s_b})
            pair_data = student_features.get(pair_key)
            if pair_data is None:
                pair_data = student_features.get((s_a, s_b), student_features.get((s_b, s_a), {}))

            incidents = int(pair_data.get("past_incidents_together", 0))
            classes = int(pair_data.get("shared_classes_count", 0))
            acad_sim = float(pair_data.get("academic_similarity_score", 0.5))
        else:
            if roster:
                # Neutral baseline when using real roster without explicit incident history
                incidents = 0
                classes = 0
                acad_sim = 0.5
            else:
                # Fully simulated mode
                incidents = int(rng.choice([0, 1, 2, 3], p=[0.60, 0.25, 0.10, 0.05]))
                classes = int(rng.randint(0, 6))
                acad_sim = float(np.round(rng.beta(2, 2), 4))

        feature_rows.append({
            "past_incidents_together": incidents,
            "shared_classes_count": classes,
            "academic_similarity_score": acad_sim,
            "roll_number_proximity": prox,
        })
        valid_pairs.append((s_a, s_b))

    if not valid_pairs:
        return RiskPairs([], feature_sources=feature_sources)

    features_df = pd.DataFrame(feature_rows)

    # 4. Predict conflict probabilities
    probabilities = model.predict_proba(features_df)[:, 1]

    # 5. Filter by probability threshold
    candidate_pairs = []
    for i, pair in enumerate(valid_pairs):
        if probabilities[i] >= threshold:
            candidate_pairs.append(pair)

    # 6. Apply Real-Name Privacy Safeguard
    # Filter OUT any pair where either student's name is in PROTECTED_REAL_NAMES
    high_risk_pairs = []
    excluded_count = 0

    # Build normalized lookup for protected names
    protected_normalized = {name.strip().upper() for name in PROTECTED_REAL_NAMES if name and isinstance(name, str)}

    for s_a, s_b in candidate_pairs:
        name_a = roster.get(s_a, s_a) if roster else s_a
        name_b = roster.get(s_b, s_b) if roster else s_b

        is_prot_a = (name_a in PROTECTED_REAL_NAMES) or (isinstance(name_a, str) and name_a.strip().upper() in protected_normalized)
        is_prot_b = (name_b in PROTECTED_REAL_NAMES) or (isinstance(name_b, str) and name_b.strip().upper() in protected_normalized)

        if is_prot_a or is_prot_b:
            excluded_count += 1
            logger.info(f"Privacy Safeguard: Excluded pair ({s_a}, {s_b}) with protected name ({name_a}, {name_b}).")
        else:
            high_risk_pairs.append((s_a, s_b))

    if excluded_count > 0:
        msg = f"Excluded {excluded_count} pairs involving protected real names from output."
        logger.info(msg)
        print(f"[ml_risk_model SAFEGUARD] {msg}")

    return RiskPairs(high_risk_pairs, feature_sources=feature_sources, pairs_with_real_evidence=pairs_with_real_evidence)


# =======================================================================
#  DEMO / MAIN
# =======================================================================

if __name__ == "__main__":
    print("=" * 65)
    print("  ML RISK MODEL — 4-Feature Architecture & Real Roster Integration")
    print("=" * 65)

    # -- Step 1: Generate simulated 4-feature training data -------------------
    print("\n[1/4] Generating simulated 4-feature dataset...")
    df = generate_simulated_data(num_pairs=1000)
    print(f"      Dataset shape: {df.shape}")
    print(f"      Sample rows:")
    print(df.head(5).to_string(index=False))

    # -- Step 2: Train Random Forest classifier ------------------------------
    print("\n[2/4] Training Random Forest classifier...")
    model = train_risk_model(df)

    # -- Step 3: Run inference on generic demo roster (simulated fallback) ---
    print("\n[3/4] Running inference on generic demo roster (simulated fallback)...")
    generic_roster = ["S1", "S2", "S3", "S4", "S5", "S6"]
    simulated_results = get_high_risk_pairs(model, generic_roster, threshold=0.75)
    print(f"      Generic Roster: {generic_roster}")
    print(f"      Flagged pairs: {simulated_results}")
    print(f"      Feature Sources: {simulated_results.feature_sources}")

    # -- Step 4: Run inference on class roster CSV ----------------------
    print("\n[4/4] Running inference on class roster CSV with proximity scoring...")
    roster_path = get_default_roster_path()

    if os.path.exists(roster_path):
        roster_data = load_roster(roster_path)
        print(f"      Loaded roster: {len(roster_data)} students, max USN gap = {roster_data.max_gap}")

        # Sample test cohort using USNs from the CSV
        usn_by_num = {_extract_usn_number(k): k for k in roster_data.keys()}
        keys_sorted = sorted(roster_data.keys(), key=lambda k: _extract_usn_number(k) or 0)
        usn_0005 = usn_by_num.get(5, keys_sorted[4] if len(keys_sorted) > 4 else keys_sorted[0])
        usn_0006 = usn_by_num.get(6, keys_sorted[5] if len(keys_sorted) > 5 else keys_sorted[0])
        usn_0007 = usn_by_num.get(7, keys_sorted[6] if len(keys_sorted) > 6 else keys_sorted[0])
        usn_0011 = usn_by_num.get(11, keys_sorted[10] if len(keys_sorted) > 10 else keys_sorted[0])
        usn_0050 = usn_by_num.get(50, keys_sorted[-1])

        valid_usns = [usn_0005, usn_0006, usn_0007, usn_0011, usn_0050]

        print(f"      Evaluating sample cohort: {valid_usns}")
        # Test proximity calculation directly
        prox_adjacent = compute_roll_proximity(usn_0005, usn_0006, roster_data)
        prox_distant = compute_roll_proximity(usn_0005, usn_0050, roster_data)
        print(f"      Proximity ({usn_0005} <-> {usn_0006}, adjacent): {prox_adjacent}")
        print(f"      Proximity ({usn_0005} <-> {usn_0050}, distant):  {prox_distant}")

        # Test inference with roster
        real_results = get_high_risk_pairs(
            model,
            valid_usns,
            threshold=0.50,
            roster_csv_path=roster_path,
        )
        print(f"      Flagged high-risk pairs (threshold=0.50): {real_results}")
        print(f"      Feature Sources: {real_results.feature_sources}")

        # -- Step 5: Test Roster Validation & Mismatch Handling -------------------
        print("\n--- Testing Roster Membership Validation & Guardrails ---")
        test_typo = usn_0005[:-4] + "O" + usn_0005[-3:]
        test_mismatched = [usn_0005, test_typo, "S1", usn_0006]
        matched, unmatched = validate_roster_membership(test_mismatched, roster_data)
        print(f"      Input test IDs: {test_mismatched}")
        print(f"      Matched IDs:    {matched}")
        print(f"      Unmatched IDs:  {unmatched}")
        assert unmatched == [test_typo, "S1"], f"Unexpected unmatched: {unmatched}"

        # 5a. Strict check raises RosterMismatchError
        try:
            get_high_risk_pairs(model, test_mismatched, threshold=0.50, roster_csv_path=roster_path, strict_roster_check=True)
            raise AssertionError("Should have raised RosterMismatchError!")
        except RosterMismatchError as exc:
            print(f"      [Expected Error Caught] RosterMismatchError: {exc.unmatched_ids}")

        # 5b. Non-strict check falls back to 0.5 for unmatched pairs
        lenient_results = get_high_risk_pairs(model, test_mismatched, threshold=0.50, roster_csv_path=roster_path, strict_roster_check=False)
        print(f"      Lenient mode (strict_roster_check=False) succeeded. Flagged pairs: {lenient_results}")

        # -- Safeguard verification demo --
        print("\n--- Testing Privacy Safeguard on Protected Names ---")
        test_protected_name = roster_data.get(usn_0005, "Student_005")
        PROTECTED_REAL_NAMES.add(test_protected_name)
        print("      Added test protected name to PROTECTED_REAL_NAMES.")

        filtered_results = get_high_risk_pairs(
            model,
            valid_usns,
            threshold=0.50,
            roster_csv_path=roster_path,
        )
        print(f"      Pairs after safeguard filtering: {filtered_results}")
        for pair in filtered_results:
            assert usn_0005 not in pair, f"Safeguard violation: {pair} contains protected student!"
        print("      Safeguard verification: PASSED! Zero protected names in output.")

        # Reset safeguard set
        PROTECTED_REAL_NAMES.discard(test_protected_name)
    else:
        print(f"      CSV not found at {roster_path}")

    print("\n" + "=" * 65)
    print("  Demo Complete.")
    print("=" * 65)
