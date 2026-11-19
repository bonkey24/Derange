"""
seating/urls.py
---------------
URL routing for the seating application.
Uses DRF DefaultRouter for ModelViewSets and path() for calculation action endpoints.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

# DRF router for standard CRUD endpoints
router = DefaultRouter()
router.register(r'rooms', views.RoomViewSet, basename='room')
router.register(r'students', views.StudentViewSet, basename='student')
router.register(r'conflict-pairs', views.ConstraintConflictPairViewSet, basename='conflict-pair')
router.register(r'forbidden-constraints', views.ConstraintForbiddenViewSet, basename='forbidden-constraint')

urlpatterns = [
    # Router CRUD endpoints (e.g. /api/rooms/, /api/students/, etc.)
    path('', include(router.urls)),

    # Dedicated mathematical & ML calculation endpoints
    path('generate-seating/', views.generate_seating_chart, name='generate-seating'),
    path('generate-retest/', views.generate_retest, name='generate-retest'),
    path('train-risk-model/', views.train_risk_model_api, name='train-risk-model'),
    path('seating-results/<int:room_id>/', views.seating_results_by_room, name='seating-results-by-room'),
    path('math-explainer/<int:room_id>/', views.math_explainer, name='math-explainer'),
    path('math-explainer/<int:room_id>/tiny-proof/', views.tiny_proof_explainer, name='math-explainer-tiny-proof'),

    # Department roster endpoints
    path('rosters/', views.list_rosters, name='list-rosters'),
    path('rosters/<slug:slug>/', views.get_roster_detail, name='get-roster-detail'),
    path('rooms/<int:room_id>/add-roster-students/', views.add_roster_students_to_room, name='add-roster-students'),
]
