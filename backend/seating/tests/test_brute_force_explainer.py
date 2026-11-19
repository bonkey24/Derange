"""
test_brute_force_explainer.py
------------------------------
Unit and integration tests for the Tiny-Room proof brute-force permutation explainer.
Tests:
- totals = n!
- valid counts equal inclusion-exclusion engine's results across several boards
- D3 = 2 and D4 = 9 derangement exact matches
- n > 5 error handling
- API endpoint GET /api/math-explainer/<room_id>/tiny-proof/ for real rooms (n <= 5)
  and fallback mini example for large rooms (n > 5).
"""

import math
import pytest
from rest_framework.test import APIClient
from django.urls import reverse

from seating.models import Room, Student, ConstraintForbidden
from seating.engines.brute_force_explainer import enumerate_arrangements


class TestBruteForceExplainerEngine:

    def test_totals_equal_n_factorial(self):
        for n in range(1, 6):
            res = enumerate_arrangements(n, mode="seating")
            expected_n_fact = math.factorial(n)
            assert res["all"] == expected_n_fact
            assert res["total_arrangements"] == expected_n_fact
            assert len(res["arrangements"]) == expected_n_fact
            assert res["valid"] + res["invalid"] == expected_n_fact

    def test_valid_counts_match_inclusion_exclusion(self):
        # Board 1: 0 forbidden cells (all permutations valid)
        res_0 = enumerate_arrangements(3, [], mode="seating")
        assert res_0["valid"] == 6
        assert res_0["matches"] is True

        # Board 2: 1 forbidden cell on 3x3 board
        # 3! - 1 * 2! = 6 - 2 = 4
        res_1 = enumerate_arrangements(3, [(0, 0)], mode="seating")
        assert res_1["valid"] == 4
        assert res_1["formula_value"] == 4
        assert res_1["matches"] is True

        # Board 3: 2 independent forbidden cells on 4x4 board
        # 4! - 2*3! + 1*2! = 24 - 12 + 2 = 14
        res_2 = enumerate_arrangements(4, [(0, 0), (1, 1)], mode="seating")
        assert res_2["all"] == 24
        assert res_2["valid"] == 14
        assert res_2["invalid"] == 10
        assert res_2["formula_value"] == 14
        assert res_2["matches"] is True

        # Board 4: 2 collinear forbidden cells (sharing row)
        # 4! - 2*3! + 0 = 24 - 12 = 12
        res_collinear = enumerate_arrangements(4, [(0, 0), (0, 1)], mode="seating")
        assert res_collinear["valid"] == 12
        assert res_collinear["formula_value"] == 12
        assert res_collinear["matches"] is True

        # Board 5: 3 independent forbidden cells on 4x4 board
        # 4! - 3*3! + 3*2! - 1*1! = 24 - 18 + 6 - 1 = 11
        res_3 = enumerate_arrangements(4, [(0, 0), (1, 1), (2, 2)], mode="seating")
        assert res_3["valid"] == 11
        assert res_3["formula_value"] == 11
        assert res_3["matches"] is True

        # Board 6: 2 forbidden cells on 5x5 board
        # 5! - 2*4! + 1*3! = 120 - 48 + 6 = 78
        res_5 = enumerate_arrangements(5, [(0, 0), (1, 1)], mode="seating")
        assert res_5["all"] == 120
        assert res_5["valid"] == 78
        assert res_5["formula_value"] == 78
        assert res_5["matches"] is True

    def test_derangements_d3_and_d4(self):
        # n = 3: D(3) = 2
        res_d3 = enumerate_arrangements(3, mode="retest")
        assert res_d3["all"] == 6
        assert res_d3["valid"] == 2
        assert res_d3["invalid"] == 4
        assert res_d3["formula_value"] == 2
        assert res_d3["matches"] is True

        # Confirm the exact 2 valid derangements for n = 3
        valid_assignments = [
            a["assignment"] for a in res_d3["arrangements"] if a["is_valid"]
        ]
        assert "S1->2, S2->3, S3->1" in valid_assignments
        assert "S1->3, S2->1, S3->2" in valid_assignments

        # n = 4: D(4) = 9
        res_d4 = enumerate_arrangements(4, mode="retest")
        assert res_d4["all"] == 24
        assert res_d4["valid"] == 9
        assert res_d4["invalid"] == 15
        assert res_d4["formula_value"] == 9
        assert res_d4["matches"] is True

        # n = 5: D(5) = 44
        res_d5 = enumerate_arrangements(5, mode="retest")
        assert res_d5["all"] == 120
        assert res_d5["valid"] == 44
        assert res_d5["formula_value"] == 44
        assert res_d5["matches"] is True

    def test_n_greater_than_five_raises_value_error(self):
        with pytest.raises(ValueError) as exc:
            enumerate_arrangements(6)
        assert "restricted to n <= 5" in str(exc.value)


@pytest.mark.django_db
class TestTinyProofAPIEndpoint:

    @pytest.fixture(autouse=True)
    def setup_client(self):
        self.client = APIClient()

    def test_api_real_room_n_less_or_equal_five(self):
        room = Room.objects.create(name="Tiny Room 4", rows=2, cols=2)
        s1 = Student.objects.create(room=room, roll_no="TINY_01", name="Alpha")
        s2 = Student.objects.create(room=room, roll_no="TINY_02", name="Beta")
        s3 = Student.objects.create(room=room, roll_no="TINY_03", name="Gamma")
        s4 = Student.objects.create(room=room, roll_no="TINY_04", name="Delta")

        # 2 forbidden cells in different rows & cols
        ConstraintForbidden.objects.create(room=room, student=s1, seat_index=0)
        ConstraintForbidden.objects.create(room=room, student=s2, seat_index=1)

        url = reverse("math-explainer-tiny-proof", kwargs={"room_id": room.id})
        response = self.client.get(url)
        assert response.status_code == 200
        data = response.json()

        assert data["is_mini_example"] is False
        assert data["reason"] is None
        assert data["room_students_count"] == 4

        seating = data["seating"]
        assert seating["all"] == 24
        assert seating["valid"] == 14
        assert seating["matches"] is True
        assert len(seating["arrangements"]) == 24

        retest = data["retest"]
        assert retest["all"] == 24
        assert retest["valid"] == 9  # D(4) = 9
        assert retest["matches"] is True

    def test_api_fallback_for_large_room_n_greater_than_five(self):
        room = Room.objects.create(name="Large Room 12", rows=3, cols=4)
        for i in range(12):
            Student.objects.create(
                room=room, roll_no=f"LARGE_{i:02d}", name=f"Student {i}"
            )

        url = reverse("math-explainer-tiny-proof", kwargs={"room_id": room.id})
        response = self.client.get(url)
        assert response.status_code == 200
        data = response.json()

        assert data["is_mini_example"] is True
        assert "larger than 5" in data["reason"]
        assert data["room_students_count"] == 12

        # Built-in seating mini example: n = 4 with 2 forbidden cells
        seating = data["seating"]
        assert seating["n"] == 4
        assert seating["all"] == 24
        assert seating["valid"] == 14
        assert seating["matches"] is True

        # Derangement mini examples: D3 = 2, D4 = 9
        retest_n3 = data["retest_n3"]
        assert retest_n3["n"] == 3
        assert retest_n3["all"] == 6
        assert retest_n3["valid"] == 2
        assert retest_n3["matches"] is True

        retest_n4 = data["retest_n4"]
        assert retest_n4["n"] == 4
        assert retest_n4["all"] == 24
        assert retest_n4["valid"] == 9
        assert retest_n4["matches"] is True
