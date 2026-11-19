"""
rosters.py
----------
Department roster loading, validation, and slug management for Derange.

Loads department CSV files from backend/seating/data/rosters/ (or ROSTER_DIR override).
Validates column headers, non-empty and unique USNs, and UTF-8 with BOM support.
"""

import csv
import glob
import logging
import os
import re

logger = logging.getLogger(__name__)

DEFAULT_ROSTER_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'data', 'rosters'
)


def get_roster_dir(override_dir=None):
    """
    Returns the active roster directory, honoring override arguments
    or the ROSTER_DIR environment variable.
    """
    if override_dir:
        return os.path.abspath(override_dir)
    env_dir = os.environ.get('ROSTER_DIR')
    if env_dir:
        return os.path.abspath(env_dir)
    return DEFAULT_ROSTER_DIR


def slugify_department(label: str) -> str:
    """
    Generate a clean URL-safe slug from a department file name.
    Example: 'CSE - AIDD' -> 'cse-aidd'
             'CSE - AIML - D' -> 'cse-aiml-d'
             'ISE' -> 'ise'
    """
    clean = re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')
    return clean or 'unnamed'


def _find_column(headers, candidates):
    """
    Case-insensitive search for an expected column in headers.
    """
    for idx, header in enumerate(headers):
        if not header:
            continue
        normalized = header.strip().lower()
        if normalized in candidates:
            return idx
    # Fallback substring matching if exact match not found
    for idx, header in enumerate(headers):
        if not header:
            continue
        normalized = header.strip().lower()
        for cand in candidates:
            if cand in normalized:
                return idx
    return None


class LoadRostersResult(tuple):
    """
    Tuple of (rosters_by_slug, errors) supporting attribute and string-key access.
    """
    def __new__(cls, rosters, errors):
        return super().__new__(cls, (rosters, errors))

    @property
    def rosters(self):
        return self[0]

    @property
    def errors(self):
        return self[1]

    def __getitem__(self, key):
        if isinstance(key, str):
            if key == 'rosters':
                return self[0]
            if key == 'errors':
                return self[1]
            raise KeyError(key)
        return super().__getitem__(key)


def load_all_rosters(roster_dir=None):
    """
    Reads every CSV file in backend/seating/data/rosters/ (or ROSTER_DIR env override).
    
    Department label is the filename without '.csv', exactly as written.
    Each roster receives a URL-safe slug.
    
    Validates:
        - Required columns (USN and Name, case-insensitive)
        - No blank or duplicate USNs
        - UTF-8 with BOM handled
        - Completely empty lines skipped
    
    Skips invalid files and records clear error messages.
    
    Returns:
        LoadRostersResult: (rosters_by_slug, errors)
            rosters_by_slug (dict): slug -> {
                'slug': str,
                'department': str,
                'count': int,
                'students': [{'usn': str, 'name': str}, ...],
                'file_path': str,
            }
            errors (list[str]): List of error descriptions for skipped files.
    """
    target_dir = get_roster_dir(roster_dir)
    rosters_by_slug = {}
    errors = []

    if not os.path.isdir(target_dir):
        logger.warning(f"Roster directory does not exist: {target_dir}")
        return LoadRostersResult(rosters_by_slug, errors)

    csv_files = sorted(glob.glob(os.path.join(target_dir, '*.csv')))

    for file_path in csv_files:
        file_name = os.path.basename(file_path)
        department_label, _ = os.path.splitext(file_name)
        slug = slugify_department(department_label)

        try:
            with open(file_path, mode='r', encoding='utf-8-sig', newline='') as f:
                reader = csv.reader(f)
                try:
                    headers = next(reader)
                except StopIteration:
                    errors.append(f"{file_name}: Empty CSV file.")
                    continue

                if not headers:
                    errors.append(f"{file_name}: Missing header row.")
                    continue

                usn_idx = _find_column(headers, {
                    'usn', 'usn number', 'usn_number', 'roll no', 'roll_no', 'roll number', 'rollno', 'student_id'
                })
                name_idx = _find_column(headers, {
                    'name', 'student name', 'student_name', 'full name', 'fullname', 'student full name'
                })

                if usn_idx is None:
                    errors.append(
                        f"{file_name}: Missing required column for USN/Roll Number."
                    )
                    continue

                if name_idx is None:
                    errors.append(
                        f"{file_name}: Missing required column for Student Name."
                    )
                    continue

                students = []
                seen_usns = set()
                file_has_error = False

                for row_idx, row in enumerate(reader, start=2):
                    # Skip completely empty rows
                    if not row or not any(cell and cell.strip() for cell in row):
                        continue

                    usn = row[usn_idx].strip() if usn_idx < len(row) else ''
                    name = row[name_idx].strip() if name_idx < len(row) else ''

                    if not usn:
                        errors.append(f"{file_name}: Blank USN found on row {row_idx}.")
                        file_has_error = True
                        break

                    if usn in seen_usns:
                        errors.append(
                            f"{file_name}: Duplicate USN '{usn}' found on row {row_idx}."
                        )
                        file_has_error = True
                        break

                    seen_usns.add(usn)
                    students.append({'usn': usn, 'name': name})

                if file_has_error:
                    continue

                rosters_by_slug[slug] = {
                    'slug': slug,
                    'department': department_label,
                    'count': len(students),
                    'students': students,
                    'file_path': file_path,
                }

        except Exception as e:
            logger.error(f"Error reading roster file {file_path}: {e}")
            errors.append(f"{file_name}: Error reading file: {str(e)}")

    return LoadRostersResult(rosters_by_slug, errors)
