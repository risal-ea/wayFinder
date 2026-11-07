import pytest
from apps.providers.mock_client import MockTravelProvider
from apps.providers.affiliate import BookingAffiliateService
from apps.catalog.services.ingestion import TravelIngestionService
from apps.catalog.models import FlightOffer, MasterHotel

def test_booking_affiliate_service():
    service = BookingAffiliateService(affiliate_id="test_aid_123")
    url = service.build_hotel_deep_link(
        hotel_name="Park Hyatt",
        city="Tokyo",
        check_in_date="2026-05-10",
        check_out_date="2026-05-15",
        guests=2
    )
    assert "booking.com" in url
    assert "aid=test_aid_123" in url
    assert "Park+Hyatt" in url or "Park%20Hyatt" in url
    assert "checkin=2026-05-10" in url

def test_mock_provider_flights():
    provider = MockTravelProvider()
    flights = provider.search_flights(
        origin="JFK",
        destination="NRT",
        departure_date="2026-05-10",
        passengers=1
    )
    assert len(flights) >= 1
    first = flights[0]
    assert first["origin_iata"] == "JFK"
    assert first["destination_iata"] == "NRT"
    assert first["total_amount"] > 0

def test_mock_provider_hotels():
    provider = MockTravelProvider()
    hotels = provider.search_hotels(
        city_code="TYO",
        check_in_date="2026-05-10",
        check_out_date="2026-05-15",
        guests=1
    )
    assert len(hotels) >= 1
    first = hotels[0]
    assert "affiliate_booking_url" in first
    assert "booking.com" in first["affiliate_booking_url"]

@pytest.mark.django_db
def test_travel_ingestion_service():
    provider = MockTravelProvider()
    ingestion = TravelIngestionService(provider=provider)

    # Ingest flights
    offers = ingestion.ingest_flights(
        origin="JFK",
        destination="NRT",
        departure_date="2026-05-10",
        passengers=1
    )
    assert len(offers) >= 1
    assert FlightOffer.objects.filter(origin_airport__iata_code="JFK").exists()

    # Ingest hotels
    hotels = ingestion.ingest_hotels(
        city_code="TYO",
        check_in_date="2026-05-10",
        check_out_date="2026-05-15",
    )
    assert len(hotels) >= 1
    assert MasterHotel.objects.filter(city="Tokyo").exists()

