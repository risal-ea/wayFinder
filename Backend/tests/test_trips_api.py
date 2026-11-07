import pytest
from rest_framework.test import APIClient
from apps.trips.models import Trip, ItineraryDay

@pytest.mark.django_db
def test_trip_crud():
    client = APIClient()
    response = client.post('/api/trips/', {
        "title": "Spring in Tokyo",
        "origin_city": "JFK",
        "destination_city": "Tokyo",
        "start_date": "2026-05-01",
        "end_date": "2026-05-06",
        "passenger_count": 1,
        "budget_ceiling": "2500.00",
        "currency": "USD"
    }, format='json')
    assert response.status_code == 201
    trip_id = response.data['id']

    # Retrieve trip
    get_res = client.get(f'/api/trips/{trip_id}/')
    assert get_res.status_code == 200
    assert get_res.data['title'] == "Spring in Tokyo"

    # Add day to trip
    day_res = client.post(f'/api/trips/{trip_id}/add_day/', {
        "day_number": 1,
        "date": "2026-05-01",
        "theme": "Arrival & Shibuya Crossing",
        "activities_json": [{"time_of_day": "evening", "title": "Shibuya Crossing", "location": "Shibuya"}],
        "day_cost_estimate": "50.00"
    }, format='json')
    assert day_res.status_code == 201
    assert len(day_res.data['days']) == 1

@pytest.mark.django_db
def test_search_flights_api():
    client = APIClient()
    response = client.post('/api/trips/flights/search/', {
        "origin": "JFK",
        "destination": "NRT",
        "departure_date": "2026-05-01"
    }, format='json')
    assert response.status_code == 200
    assert response.data['count'] > 0

@pytest.mark.django_db
def test_workspace_view():
    client = APIClient()
    response = client.get('/')
    assert response.status_code == 200
    assert b"Wayfinder AI" in response.content

@pytest.mark.django_db
def test_api_root():
    client = APIClient()
    response = client.get('/api/')
    assert response.status_code == 200
    assert response.json()["status"] == "operational"
