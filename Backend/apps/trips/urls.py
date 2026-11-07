from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TripViewSet,
    SearchFlightsAPIView,
    SearchHotelsAPIView,
    AirportsListAPIView,
)

router = DefaultRouter()
router.register(r'', TripViewSet, basename='trip')

urlpatterns = [
    path('flights/search/', SearchFlightsAPIView.as_view(), name='flights-search'),
    path('hotels/search/', SearchHotelsAPIView.as_view(), name='hotels-search'),
    path('airports/', AirportsListAPIView.as_view(), name='airports-list'),
    path('', include(router.urls)),
]

