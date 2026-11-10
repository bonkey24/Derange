"""
models.py
----------
Database models for the seating allocation system.

Five models capture the full problem domain:
    - Room:                   the physical classroom grid
    - Student:                individual students
    - ConstraintForbidden:    "student X cannot sit in seat Y" (Layer 1)
    - ConstraintConflictPair: "students A and B must not sit adjacent" (Layer 2)
    - SeatingResult:          saved output of a seating generation run
"""

from django.db import models


class Room(models.Model):
    """
    A physical classroom represented as a rectangular grid of seats.
    The total number of seats is rows * cols.
    Seats are indexed linearly: seat_index = row * cols + col.
    """
    name = models.CharField(max_length=100)
    rows = models.PositiveIntegerField()
    cols = models.PositiveIntegerField()

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.rows}x{self.cols})"

    @property
    def total_seats(self):
        return self.rows * self.cols


class Student(models.Model):
    """
    An individual student.  roll_no is unique and serves as the student
    identifier in the engine modules (e.g., "S1", "S2").
    """
    name = models.CharField(max_length=100)
    roll_no = models.CharField(max_length=20, unique=True)

    class Meta:
        ordering = ['roll_no']

    def __str__(self):
        return f"{self.roll_no} - {self.name}"


class ConstraintForbidden(models.Model):
    """
    Layer 1 constraint: student X is forbidden from sitting in seat Y
    within a specific room.  Maps directly to a (student_idx, seat_idx)
    tuple in the rook polynomial's forbidden board.

    Examples: accessibility issues, proctoring sight-line problems.
    """
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='forbidden_seats'
    )
    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name='forbidden_constraints'
    )
    seat_index = models.PositiveIntegerField()

    class Meta:
        unique_together = ('student', 'room', 'seat_index')
        ordering = ['room', 'student', 'seat_index']

    def __str__(self):
        return f"{self.student.roll_no} forbidden from seat {self.seat_index} in {self.room.name}"


class ConstraintConflictPair(models.Model):
    """
    Layer 2 constraint: students A and B must NOT be seated adjacent
    to each other in a specific room.  Maps directly to a
    (student_a, student_b) tuple in the backtracking solver's
    conflict_pairs parameter.

    Examples: known cheating partners, disruptive pair.
    """
    student_a = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='conflicts_as_a'
    )
    student_b = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name='conflicts_as_b'
    )
    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name='conflict_constraints'
    )

    class Meta:
        unique_together = ('student_a', 'student_b', 'room')
        ordering = ['room', 'student_a', 'student_b']

    def __str__(self):
        return (f"{self.student_a.roll_no} <-> {self.student_b.roll_no} "
                f"in {self.room.name}")


class SeatingResult(models.Model):
    """
    Saved output of a seating generation run.

    assignment is stored as a JSON object: {"seat_index": "student_roll_no", ...}
    This matches the dict format returned by the engine functions.

    type distinguishes between normal first-exam seatings and retest
    re-seatings (which have the additional derangement constraint).
    """
    TYPE_CHOICES = [
        ('normal', 'Normal'),
        ('retest', 'Retest'),
    ]

    room = models.ForeignKey(
        Room, on_delete=models.CASCADE, related_name='seating_results'
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    assignment = models.JSONField()
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='normal')

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.room.name} - {self.type} @ {self.generated_at:%Y-%m-%d %H:%M}"
