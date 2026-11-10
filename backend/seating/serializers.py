"""
seating/serializers.py
-----------------------
Clean DRF ModelSerializers for Room, Student, ConstraintConflictPair,
ConstraintForbidden, and SeatingResult.
"""

from rest_framework import serializers
from .models import (
    Room,
    Student,
    ConstraintForbidden,
    ConstraintConflictPair,
    SeatingResult,
)


class RoomSerializer(serializers.ModelSerializer):
    """
    Serializer for the physical classroom room grid.
    Exposes total_seats as a read-only computed property (rows * cols).
    """
    total_seats = serializers.ReadOnlyField()

    class Meta:
        model = Room
        fields = ['id', 'name', 'rows', 'cols', 'total_seats']


class StudentSerializer(serializers.ModelSerializer):
    """
    Serializer for student records. roll_no is unique and serves as
    the invariant key for mathematical engines.
    """
    class Meta:
        model = Student
        fields = ['id', 'name', 'roll_no']


class ConstraintForbiddenSerializer(serializers.ModelSerializer):
    """
    Serializer for individual forbidden seat constraints (Layer 1).
    Maps to forbidden cells on the rook polynomial board.
    """
    student_roll_no = serializers.CharField(source='student.roll_no', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)

    class Meta:
        model = ConstraintForbidden
        fields = [
            'id',
            'student',
            'student_roll_no',
            'room',
            'room_name',
            'seat_index',
        ]


class ConstraintConflictPairSerializer(serializers.ModelSerializer):
    """
    Serializer for pairwise student adjacency conflicts (Layer 2).
    Prevents student_a and student_b from being seated adjacent.
    """
    student_a_roll_no = serializers.CharField(source='student_a.roll_no', read_only=True)
    student_b_roll_no = serializers.CharField(source='student_b.roll_no', read_only=True)
    room_name = serializers.CharField(source='room.name', read_only=True)

    class Meta:
        model = ConstraintConflictPair
        fields = [
            'id',
            'student_a',
            'student_a_roll_no',
            'student_b',
            'student_b_roll_no',
            'room',
            'room_name',
        ]


class SeatingResultSerializer(serializers.ModelSerializer):
    """
    Serializer for generated seating assignments (Normal and Retest).
    assignment stores the JSON mapping {"seat_index": "roll_no"}.
    """
    room_name = serializers.CharField(source='room.name', read_only=True)

    class Meta:
        model = SeatingResult
        fields = [
            'id',
            'room',
            'room_name',
            'generated_at',
            'assignment',
            'type',
        ]
        read_only_fields = ['generated_at']
