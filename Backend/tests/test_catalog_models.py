import datetime
from decimal import Decimal
import pytest
from django.utils import timezone
from apps.catalog.models import Airport, MasterHotel, FlightOffer

@pytest.mark.django_db
def test_airport_creation():
    airport = Airport.objects.create(
        iata_code="NRT",
        name="Narita International Airport",
        city_name="Tokyo",
        country_code="JP",
        latitude=Decimal("35.7720"),
        longitude=Decimal("140.3929"),
    )
    assert airport.iata_code == "NRT"
    assert "Tokyo" in str(airport)

@pytest.mark.django_db
def test_master_hotel_creation():
    hotel = MasterHotel.objects.create(
        name="Park Hyatt Tokyo",
        city="Tokyo",
        neighborhood="Shinjuku",
        star_rating=Decimal("5.0"),
        review_score=Decimal("9.4"),
        price_per_night=Decimal("450.00"),
        amadeus_hotel_id="TYOPHT01",
    )
    assert hotel.name == "Park Hyatt Tokyo"
    assert hotel.price_per_night == Decimal("450.00")

@pytest.mark.django_db
def test_flight_offer_expiration():
    jfk = Airport.objects.create(
        iata_code="JFK", name="JFK", city_name="New York", country_code="US",
        latitude=Decimal("40.64"), longitude=Decimal("-73.77")
    )
    nrt = Airport.objects.create(
        iata_code="NRT", name="NRT", city_name="Tokyo", country_code="JP",
        latitude=Decimal("35.77"), longitude=Decimal("140.39")
    )
    now = timezone.now()
    
    # Active offer
    active_offer = FlightOffer.objects.create(
        airline_name="ANA",
        flight_number="NH009",
        origin_airport=jfk,
        destination_airport=nrt,
        departure_time=now + datetime.timedelta(days=1),
        arrival_time=now + datetime.timedelta(days=1, hours=14),
        duration_minutes=840,
        total_amount=Decimal("950.00"),
        expires_at=now + datetime.timedelta(minutes=20),
    )
    assert not active_offer.is_expired

    # Expired offer
    expired_offer = FlightOffer.objects.create(
        airline_name="JAL",
        flight_number="JL005",
        origin_airport=jfk,
        destination_airport=nrt,
        departure_time=now + datetime.timedelta(days=1),
        arrival_time=now + datetime.timedelta(days=1, hours=14),
        duration_minutes=840,
        total_amount=Decimal("980.00"),
        expires_at=now - datetime.timedelta(minutes=1),
    )
    assert expired_offer.is_expired

