"""
admin.py
---------
Register all models with Django admin for quick data inspection and
manual data entry during development.
"""

from django.contrib import admin
from .models import (
    Room, Student, ConstraintForbidden, ConstraintConflictPair, SeatingResult,
)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'rows', 'cols', 'total_seats']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['roll_no', 'name']
    search_fields = ['roll_no', 'name']


@admin.register(ConstraintForbidden)
class ConstraintForbiddenAdmin(admin.ModelAdmin):
    list_display = ['student', 'room', 'seat_index']
    list_filter = ['room']


@admin.register(ConstraintConflictPair)
class ConstraintConflictPairAdmin(admin.ModelAdmin):
    list_display = ['student_a', 'student_b', 'room']
    list_filter = ['room']


@admin.register(SeatingResult)
class SeatingResultAdmin(admin.ModelAdmin):
    list_display = ['room', 'type', 'generated_at']
    list_filter = ['room', 'type']
    readonly_fields = ['generated_at']
