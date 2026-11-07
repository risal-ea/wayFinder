"""
URL Configuration for Wayfinder AI Centralized Travel Operating System.
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.http import JsonResponse

def workspace_view(request):
    """Renders the interactive split-screen workspace frontend."""
    return render(request, 'workspace.html')

def api_root(request):
    return JsonResponse({
        "service": "Wayfinder AI Travel Operating System",
        "status": "operational",
        "version": "1.0.0",
        "endpoints": {
            "workspace": "/",
            "admin": "/admin/",
            "trips": "/api/trips/",
            "flights_search": "/api/trips/flights/search/",
            "hotels_search": "/api/trips/hotels/search/",
            "airports": "/api/trips/airports/",
            "bookings": "/api/bookings/",
            "agents_chat": "/api/agents/chat/",
            "agents_plan": "/api/agents/plan/",
            "mcp_tools": "/api/agents/tools/",
        }
    })

urlpatterns = [
    path('', workspace_view, name='workspace'),
    path('api/', api_root, name='api-root'),
    path('admin/', admin.site.urls),
    path('api/trips/', include('apps.trips.urls')),
    path('api/bookings/', include('apps.bookings.urls')),
    path('api/agents/', include('apps.agents.urls')),
]
