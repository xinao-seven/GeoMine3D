from django.urls import path, include
from django.conf import settings
from django.views.static import serve
import os

urlpatterns = [
    path('api/', include('apps.geology.urls')),
]

# Serve static files from all STATICFILES_DIRS in development
for static_dir in getattr(settings, 'STATICFILES_DIRS', []):
    urlpatterns += [
        path(
            settings.STATIC_URL.lstrip('/') + '<path:path>',
            serve,
            {'document_root': str(static_dir)},
        ),
    ]
    break  # Only register the route once; serve picks the first matching dir
