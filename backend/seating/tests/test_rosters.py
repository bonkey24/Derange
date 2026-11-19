"""
test_rosters.py
---------------
Unit tests for department roster loading, validation, slugification,
API endpoints, duplicate skipping, and capacity enforcement.
Uses pytest tmp_path to create small fake CSV fixtures with fake names and USNs.
"""

import os
import pytest
from rest_framework.test import APIClient
from django.urls import reverse

from seating.rosters import (
    load_all_rosters,
    slugify_department,
    get_roster_dir,
)
from seating.models import Room, Student
from seating.engines.ml_risk_model import (
    load_roster,
    get_high_risk_pairs,
    RosterMismatchError,
    generate_simulated_data,
    train_risk_model,
)


# =======================================================================
# 1. LOADER TESTS (with tmp_path fake CSVs)
# =======================================================================

class TestRosterLoader:

    def test_slugify_department(self):
        assert slugify_department("CSE - AIDD") == "cse-aidd"
        assert slugify_department("CSE - AIML - D") == "cse-aiml-d"
        assert slugify_department("CSE - AIML - E") == "cse-aiml-e"
        assert slugify_department("CSE - CSBS") == "cse-csbs"
        assert slugify_department("CSE - PwC") == "cse-pwc"
        assert slugify_department("ISE") == "ise"
        assert slugify_department("ECE / Section A") == "ece-section-a"

    def test_load_valid_csv(self, tmp_path):
        csv_file = tmp_path / "TEST - DEPT.csv"
        csv_file.write_text(
            "USN,Name\nTEST001,Student One\nTEST002,Student Two\n",
            encoding="utf-8"
        )
        rosters, errors = load_all_rosters(roster_dir=str(tmp_path))
        assert len(errors) == 0
        assert "test-dept" in rosters
        assert rosters["test-dept"]["department"] == "TEST - DEPT"
        assert rosters["test-dept"]["count"] == 2
        assert rosters["test-dept"]["students"] == [
            {"usn": "TEST001", "name": "Student One"},
            {"usn": "TEST002", "name": "Student Two"},
        ]

    def test_load_utf8_with_bom(self, tmp_path):
        csv_file = tmp_path / "BOM - DEPT.csv"
        csv_file.write_text(
            "USN NUMBER,NAME\nBOM001,Student Alpha\n",
            encoding="utf-8-sig"
        )
        rosters, errors = load_all_rosters(roster_dir=str(tmp_path))
        assert len(errors) == 0
        assert "bom-dept" in rosters
        assert rosters["bom-dept"]["count"] == 1
        assert rosters["bom-dept"]["students"][0]["usn"] == "BOM001"

    def test_blank_lines_skipped(self, tmp_path):
        csv_file = tmp_path / "SPARSE.csv"
        csv_file.write_text(
            "USN,Name\n\nTEST001,Student A\n,\n   ,   \nTEST002,Student B\n\n",
            encoding="utf-8"
        )
        rosters, errors = load_all_rosters(roster_dir=str(tmp_path))
        assert len(errors) == 0
        assert rosters["sparse"]["count"] == 2

    def test_missing_usn_column_fails_file(self, tmp_path):
        csv_file = tmp_path / "BAD - NOUSN.csv"
        csv_file.write_text(
            "Identifier,Name\n123,Student A\n",
            encoding="utf-8"
        )
        rosters, errors = load_all_rosters(roster_dir=str(tmp_path))
        assert len(rosters) == 0
        assert len(errors) == 1
        assert "Missing required column" in errors[0]

    def test_missing_name_column_fails_file(self, tmp_path):
        csv_file = tmp_path / "BAD - NONAME.csv"
        csv_file.write_text(
            "USN,Scores\nTEST001,95\n",
            encoding="utf-8"
        )
        rosters, errors = load_all_rosters(roster_dir=str(tmp_path))
        assert len(rosters) == 0
        assert len(errors) == 1
        assert "Missing required column" in errors[0]

    def test_blank_usn_fails_file(self, tmp_path):
        csv_file = tmp_path / "BAD - BLANKUSN.csv"
        csv_file.write_text(
            "USN,Name\nTEST001,Student One\n,Student Two Without USN\n",
            encoding="utf-8"
        )
        rosters, errors = load_all_rosters(roster_dir=str(tmp_path))
        assert len(rosters) == 0
        assert len(errors) == 1
        assert "Blank USN" in errors[0]

    def test_duplicate_usn_fails_file(self, tmp_path):
        csv_file = tmp_path / "BAD - DUPUSN.csv"
        csv_file.write_text(
            "USN,Name\nTEST001,Student One\nTEST001,Student One Duplicate\n",
            encoding="utf-8"
        )
        rosters, errors = load_all_rosters(roster_dir=str(tmp_path))
        assert len(rosters) == 0
        assert len(errors) == 1
        assert "Duplicate USN" in errors[0]

    def test_env_dir_override(self, tmp_path, monkeypatch):
        csv_file = tmp_path / "ENV - DEPT.csv"
        csv_file.write_text("USN,Name\nENV001,Student E\n", encoding="utf-8")
        monkeypatch.setenv("ROSTER_DIR", str(tmp_path))
        rosters, errors = load_all_rosters()
        assert "env-dept" in rosters

    def test_header_variations_with_tmp_path(self, tmp_path):
        """Test case-insensitive mapping of diverse header formats across departments."""
        # Variation 1: Reverse column order ('Student Name', 'USN') as in CSE - AIML - E
        (tmp_path / "DEPT - ONE.csv").write_text(
            "Student Name,USN\nStudent Alpha,USN001\n", encoding="utf-8"
        )
        # Variation 2: Full descriptive header as in CSE - CSBS
        (tmp_path / "DEPT - TWO.csv").write_text(
            "USN NUMBER,STUDENT FULL NAME (AS PER 10TH MARKS SHEET)\nUSN002,Student Beta\n", encoding="utf-8"
        )
        # Variation 3: Standard USN, Name
        (tmp_path / "DEPT - THREE.csv").write_text(
            "USN,Name\nUSN003,Student Gamma\n", encoding="utf-8"
        )

        rosters, errors = load_all_rosters(roster_dir=str(tmp_path))
        assert len(errors) == 0
        assert len(rosters) == 3
        assert rosters["dept-one"]["students"][0] == {"usn": "USN001", "name": "Student Alpha"}
        assert rosters["dept-two"]["students"][0] == {"usn": "USN002", "name": "Student Beta"}
        assert rosters["dept-three"]["students"][0] == {"usn": "USN003", "name": "Student Gamma"}

    def test_cross_department_duplicate_usn_behavior(self, tmp_path):
        """
        A USN appearing in two departments should still work in each department's list,
        and the merged roster used for the ML roll-number check must de-duplicate by USN.
        """
        (tmp_path / "DEPT - A.csv").write_text(
            "USN,Name\nSHARED_USN_01,Student A In Dept A\nONLY_A_01,Student A Only\n", encoding="utf-8"
        )
        (tmp_path / "DEPT - B.csv").write_text(
            "USN,Name\nSHARED_USN_01,Student A In Dept B\nONLY_B_01,Student B Only\n", encoding="utf-8"
        )

        rosters, errors = load_all_rosters(roster_dir=str(tmp_path))
        assert len(errors) == 0
        assert "dept-a" in rosters and "dept-b" in rosters
        # Both departments have the student in their respective roster
        assert any(s["usn"] == "SHARED_USN_01" for s in rosters["dept-a"]["students"])
        assert any(s["usn"] == "SHARED_USN_01" for s in rosters["dept-b"]["students"])

        # Merged roster for ML must deduplicate by USN
        merged = load_roster(csv_path=None)
        # When monkeypatching ROSTER_DIR
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("ROSTER_DIR", str(tmp_path))
            merged_isolated = load_roster(csv_path=None)
            assert len(merged_isolated) == 3  # SHARED_USN_01 (deduped), ONLY_A_01, ONLY_B_01
            assert "SHARED_USN_01" in merged_isolated

    def test_real_roster_directory_loads_all_six_departments(self):
        """Verifies that the default real roster directory loads all 6 departments with zero errors."""
        rosters, errors = load_all_rosters()
        assert errors == [], f"Unexpected errors loading real rosters: {errors}"
        expected_slugs = ["cse-aidd", "cse-aiml-d", "cse-aiml-e", "cse-csbs", "cse-pwc", "ise"]
        assert sorted(list(rosters.keys())) == expected_slugs
        assert rosters["cse-aidd"]["count"] == 55
        assert rosters["cse-aiml-d"]["count"] == 61
        assert rosters["cse-aiml-e"]["count"] == 58
        assert rosters["cse-csbs"]["count"] == 61
        assert rosters["cse-pwc"]["count"] == 52
        assert rosters["ise"]["count"] == 54


# =======================================================================
# 2. ENDPOINTS TESTS
# =======================================================================

@pytest.mark.django_db
class TestRosterEndpoints:

    @pytest.fixture(autouse=True)
    def setup_client(self, tmp_path, monkeypatch):
        self.client = APIClient()
        self.tmp_dir = tmp_path
        # Setup fake department rosters
        dept1 = self.tmp_dir / "CSE - AIDD.csv"
        dept1.write_text(
            "USN,Name\n25BTRA0001,Alpha One\n25BTRA0002,Alpha Two\n25BTRA0003,Alpha Three\n",
            encoding="utf-8"
        )
        dept2 = self.tmp_dir / "ISE.csv"
        dept2.write_text(
            "USN NUMBER,NAME\n25BTRIS001,Beta One\n25BTRIS002,Beta Two\n",
            encoding="utf-8"
        )
        monkeypatch.setenv("ROSTER_DIR", str(self.tmp_dir))

    def test_get_rosters_summary(self):
        url = reverse('list-rosters')
        response = self.client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert "rosters" in data
        assert "errors" in data
        slugs = [r["slug"] for r in data["rosters"]]
        assert "cse-aidd" in slugs
        assert "ise" in slugs

    def test_get_roster_detail_success(self):
        url = reverse('get-roster-detail', kwargs={'slug': 'cse-aidd'})
        response = self.client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["department"] == "CSE - AIDD"
        assert len(data["students"]) == 3
        assert data["students"][0]["usn"] == "25BTRA0001"

    def test_get_roster_detail_404(self):
        url = reverse('get-roster-detail', kwargs={'slug': 'unknown-dept'})
        response = self.client.get(url)
        assert response.status_code == 404

    def test_add_roster_students_success(self):
        room = Room.objects.create(name="Exam Hall 1", rows=3, cols=4)  # 12 seats
        url = reverse('add-roster-students', kwargs={'room_id': room.id})

        payload = {
            "slug": "cse-aidd",
            "usns": ["25BTRA0001", "25BTRA0002"]
        }
        response = self.client.post(url, payload, format='json')
        assert response.status_code == 201
        data = response.json()
        assert data["added_count"] == 2
        assert data["skipped_count"] == 0
        assert Student.objects.filter(roll_no="25BTRA0001").exists()
        assert Student.objects.filter(roll_no="25BTRA0002").exists()

    def test_add_roster_students_skips_duplicates(self):
        room = Room.objects.create(name="Exam Hall 2", rows=3, cols=4)
        # Pre-create student 1
        Student.objects.create(room=room, roll_no="25BTRA0001", name="Alpha One")

        url = reverse('add-roster-students', kwargs={'room_id': room.id})
        payload = {
            "slug": "cse-aidd",
            "usns": ["25BTRA0001", "25BTRA0002"]
        }
        response = self.client.post(url, payload, format='json')
        assert response.status_code == 201
        data = response.json()
        assert data["added_count"] == 1
        assert data["skipped_count"] == 1
        assert "25BTRA0001" in data["skipped"]
        assert Student.objects.count() == 2

    def test_add_roster_students_rejects_unknown_usns(self):
        room = Room.objects.create(name="Exam Hall 3", rows=3, cols=4)
        url = reverse('add-roster-students', kwargs={'room_id': room.id})
        payload = {
            "slug": "cse-aidd",
            "usns": ["25BTRA0001", "UNKNOWN999"]
        }
        response = self.client.post(url, payload, format='json')
        assert response.status_code == 400
        data = response.json()
        assert "UNKNOWN999" in data["unknown_usns"]
        assert Student.objects.count() == 0

    def test_add_roster_students_enforces_capacity(self):
        # Room with only 2 seats
        small_room = Room.objects.create(name="Small Room", rows=1, cols=2)
        url = reverse('add-roster-students', kwargs={'room_id': small_room.id})
        payload = {
            "slug": "cse-aidd",
            "usns": ["25BTRA0001", "25BTRA0002", "25BTRA0003"]  # 3 students > 2 seats
        }
        response = self.client.post(url, payload, format='json')
        assert response.status_code == 400
        data = response.json()
        assert "capacity" in data["error"].lower()
        assert Student.objects.count() == 0


# =======================================================================
# 3. RISK MODEL & ROSTER INTEGRATION TESTS
# =======================================================================

class TestRiskModelRosterIntegration:

    def test_load_roster_from_tmp_path(self, tmp_path):
        csv_file = tmp_path / "ROSTER.csv"
        csv_file.write_text("USN,Name\nTEST001,Student 1\nTEST005,Student 5\n", encoding="utf-8")
        roster = load_roster(str(csv_file))
        assert "TEST001" in roster
        assert "TEST005" in roster
        assert roster.max_gap == 4

    def test_roster_mismatch_raises_error(self, tmp_path):
        csv_file = tmp_path / "ROSTER.csv"
        csv_file.write_text("USN,Name\nTEST001,Student 1\n", encoding="utf-8")
        model = train_risk_model(generate_simulated_data(num_pairs=50))
        with pytest.raises(RosterMismatchError) as exc_info:
            get_high_risk_pairs(
                model=model,
                student_list=["TEST001", "NON_EXISTENT_ID"],
                roster_csv_path=str(csv_file),
                strict_roster_check=True,
            )
        assert "NON_EXISTENT_ID" in exc_info.value.unmatched_ids

    def test_roster_match_succeeds(self, tmp_path):
        csv_file = tmp_path / "ROSTER.csv"
        csv_file.write_text("USN,Name\nTEST001,Student 1\nTEST002,Student 2\n", encoding="utf-8")
        model = train_risk_model(generate_simulated_data(num_pairs=50))
        pairs = get_high_risk_pairs(
            model=model,
            student_list=["TEST001", "TEST002"],
            roster_csv_path=str(csv_file),
            strict_roster_check=True,
        )
        assert pairs.feature_sources["roll_number_proximity"] == "real"


# =======================================================================
# 4. ROOM ISOLATION TESTS
# =======================================================================

@pytest.mark.django_db
class TestRoomIsolation:
    """
    Tests ensuring room isolation:
    - Students belong to exactly one room.
    - Two rooms can contain different students.
    - The same USN can exist in two different rooms without conflict.
    - Duplicate USN within the same room is rejected.
    - GET /api/students/?room=<id> filters strictly by room.
    """

    def test_same_usn_in_two_rooms(self):
        room_a = Room.objects.create(name="Room A", rows=2, cols=2)
        room_b = Room.objects.create(name="Room B", rows=2, cols=2)

        # Enroll same USN in both Room A and Room B
        s_a = Student.objects.create(room=room_a, roll_no="25BTRA0001", name="Student One")
        s_b = Student.objects.create(room=room_b, roll_no="25BTRA0001", name="Student One")

        assert s_a.id != s_b.id
        assert s_a.room == room_a
        assert s_b.room == room_b
        assert Student.objects.filter(roll_no="25BTRA0001").count() == 2

    def test_duplicate_usn_in_same_room_rejected(self):
        room = Room.objects.create(name="Single Room", rows=2, cols=2)
        Student.objects.create(room=room, roll_no="25BTRA0001", name="Original")

        with pytest.raises(Exception):  # IntegrityError
            Student.objects.create(room=room, roll_no="25BTRA0001", name="Duplicate")

    def test_students_api_filters_by_room(self):
        client = APIClient()
        room_a = Room.objects.create(name="Room Alpha", rows=2, cols=2)
        room_b = Room.objects.create(name="Room Beta", rows=2, cols=2)

        Student.objects.create(room=room_a, roll_no="ALPHA_1", name="Student Alpha 1")
        Student.objects.create(room=room_a, roll_no="ALPHA_2", name="Student Alpha 2")
        Student.objects.create(room=room_b, roll_no="BETA_1", name="Student Beta 1")

        # Query room_a
        res_a = client.get(f'/api/students/?room={room_a.id}')
        assert res_a.status_code == 200
        rolls_a = [s['roll_no'] for s in res_a.json()]
        assert sorted(rolls_a) == ["ALPHA_1", "ALPHA_2"]

        # Query room_b
        res_b = client.get(f'/api/students/?room={room_b.id}')
        assert res_b.status_code == 200
        rolls_b = [s['roll_no'] for s in res_b.json()]
        assert rolls_b == ["BETA_1"]

    def test_add_roster_students_independent_per_room(self, tmp_path):
        client = APIClient()
        csv_file = tmp_path / "CSE - AIDD.csv"
        csv_file.write_text("USN,Name\n25BTRA0001,Student One\n25BTRA0002,Student Two\n", encoding="utf-8")

        room_a = Room.objects.create(name="Hall A", rows=3, cols=3)
        room_b = Room.objects.create(name="Hall B", rows=3, cols=3)

        # Add 25BTRA0001 to Room A
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("ROSTER_DIR", str(tmp_path))
            res_a = client.post(
                reverse('add-roster-students', kwargs={'room_id': room_a.id}),
                {"slug": "cse-aidd", "usns": ["25BTRA0001"]},
                format='json',
            )
            assert res_a.status_code == 201
            assert res_a.json()["added_count"] == 1

            # Adding 25BTRA0001 to Room B should also succeed (not skipped as duplicate)
            res_b = client.post(
                reverse('add-roster-students', kwargs={'room_id': room_b.id}),
                {"slug": "cse-aidd", "usns": ["25BTRA0001"]},
                format='json',
            )
            assert res_b.status_code == 201
            assert res_b.json()["added_count"] == 1
            assert res_b.json()["skipped_count"] == 0

            # Both rooms now have 1 student with that USN
            assert room_a.students.count() == 1
            assert room_b.students.count() == 1

