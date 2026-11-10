"""
backend/urls.py
---------------
Root URL configuration for the Seating project backend.
Wires seating.urls under the 'api/' prefix.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('seating.urls')),
]
