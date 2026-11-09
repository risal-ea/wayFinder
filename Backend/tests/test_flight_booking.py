import datetime
from decimal import Decimal
import pytest
from rest_framework.test import APIClient
from apps.catalog.models import Airport, FlightOffer
from apps.bookings.models import BookingRecord, FlightTraveler
from apps.bookings.state_machine import BookingStateMachine
from apps.agents.flight_agent import FlightSpecialistAgent

@pytest.mark.django_db
def test_round_trip_flight_search():
    agent = FlightSpecialistAgent()
    result = agent.search_and_rank_flights(
        origin="JFK",
        destination="NRT",
        departure_date="2026-05-10",
        return_date="2026-05-20",
        passengers=2,
        cabin_class="economy"
    )
    assert result["status"] == "success"
    assert result["is_round_trip"] is True
    assert len(result["all_offers"]) >= 1
    
    first = result["all_offers"][0]
    assert first["is_round_trip"] is True
    assert first["return_flight_number"] != ""
    assert first["return_departure_time"] is not None
    assert first["base_amount"] > 0
    assert first["tax_amount"] > 0
    assert len(first["segments"]) >= 2  # Outbound and inbound segments

@pytest.mark.django_db
def test_flight_specialist_agent_ranking():
    agent = FlightSpecialistAgent()
    ranked = agent.search_and_rank_flights(
        origin="JFK",
        destination="LHR",
        departure_date="2026-06-01",
        passengers=1
    )
    assert "best_overall" in ranked
    assert "cheapest" in ranked
    assert "fastest" in ranked
    assert ranked["cheapest"]["total_amount"] <= ranked["best_overall"]["total_amount"] or ranked["best_overall"]["stops"] == 0

@pytest.mark.django_db
def test_flight_travelers_and_ticketing_fsm():
    jfk = Airport.objects.create(iata_code="JFK", name="JFK", city_name="New York", country_code="US", latitude=Decimal("40.64"), longitude=Decimal("-73.77"))
    nrt = Airport.objects.create(iata_code="NRT", name="NRT", city_name="Tokyo", country_code="JP", latitude=Decimal("35.77"), longitude=Decimal("140.39"))
    
    now = datetime.datetime.now(datetime.timezone.utc)
    offer = FlightOffer.objects.create(
        airline_name="ANA",
        flight_number="NH009",
        origin_airport=jfk,
        destination_airport=nrt,
        departure_time=now + datetime.timedelta(days=7),
        arrival_time=now + datetime.timedelta(days=7, hours=14),
        duration_minutes=840,
        total_amount=Decimal("1890.00"),
        expires_at=now + datetime.timedelta(minutes=20),
    )

    # Standalone flight booking (no trip required)
    booking = BookingRecord.objects.create(
        flight_offer=offer,
        total_amount=offer.total_amount,
        currency="USD",
        item_type="flight"
    )

    fsm = BookingStateMachine(booking)
    assert booking.status == "DRAFT"

    # 1. Validate quote
    assert fsm.validate_quote() is True
    assert booking.status == "QUOTE_VALIDATED"

    # 2. Attach travelers
    travelers_payload = [
        {
            "traveler_type": "ADULT",
            "first_name": "SARA",
            "last_name": "CONNOR",
            "date_of_birth": "1992-04-12",
            "gender": "FEMALE",
            "email": "sara@example.com",
            "phone_number": "+1-555-0192",
            "passport_number": "A12345678",
            "passport_issuing_country": "USA",
            "passport_expiry_date": "2032-04-12",
            "nationality": "USA",
            "seat_preference": "WINDOW",
        },
        {
            "traveler_type": "ADULT",
            "first_name": "JOHN",
            "last_name": "CONNOR",
            "date_of_birth": "1995-02-28",
            "gender": "MALE",
            "email": "john@example.com",
            "phone_number": "+1-555-0193",
            "passport_number": "B98765432",
            "passport_issuing_country": "USA",
            "passport_expiry_date": "2031-08-15",
            "nationality": "USA",
            "seat_preference": "AISLE",
        }
    ]
    attached = fsm.attach_travelers(travelers_payload)
    assert len(attached) == 2
    assert booking.status == "PASSENGERS_ATTACHED"
    assert booking.travelers.count() == 2

    # 3. Request human approval
    token = fsm.request_approval()
    assert booking.status == "AWAITING_APPROVAL"
    assert token is not None

    # 4. Authorize and Ticket
    fsm.submit(token)
    assert booking.status == "SUBMITTED"
    assert booking.approved_by_user is True

    fsm.confirm()
    assert booking.status == "CONFIRMED"
    assert booking.provider_reference.startswith("WAYF")
    
    # Verify official E-Tickets issued for each passenger
    for traveler in booking.travelers.all():
        assert traveler.eticket_number.startswith("176-")

@pytest.mark.django_db
def test_direct_flight_booking_api():
    client = APIClient()

    # Search flights first
    search_res = client.post('/api/trips/flights/search/', {
        "origin": "JFK",
        "destination": "NRT",
        "departure_date": "2026-06-15",
        "return_date": "2026-06-25",
        "passengers": 1
    }, format='json')
    assert search_res.status_code == 200
    offer_id = search_res.data["results"][0]["id"]

    # 1. Create booking directly
    create_res = client.post('/api/bookings/', {
        "flight_offer_id": offer_id,
        "item_type": "flight",
        "total_amount": "950.00",
        "currency": "USD"
    }, format='json')
    assert create_res.status_code == 201
    booking_id = create_res.data["id"]

    # 2. Validate quote
    val_res = client.post(f'/api/bookings/{booking_id}/validate_quote/')
    assert val_res.status_code == 200
    assert val_res.data["booking"]["status"] == "QUOTE_VALIDATED"

    # 3. Attach travelers
    attach_res = client.post(f'/api/bookings/{booking_id}/attach_travelers/', {
        "travelers": [
            {
                "first_name": "ALICE",
                "last_name": "SMITH",
                "email": "alice@example.com",
                "passport_number": "P1234567"
            }
        ]
    }, format='json')
    assert attach_res.status_code == 200
    assert attach_res.data["booking"]["status"] == "PASSENGERS_ATTACHED"
    assert len(attach_res.data["booking"]["travelers"]) == 1

    # 4. Request approval
    req_res = client.post(f'/api/bookings/{booking_id}/request_approval/')
    assert req_res.status_code == 200
    approval_token = req_res.data["approval_token"]

    # 5. Approve and issue e-ticket
    approve_res = client.post(f'/api/bookings/{booking_id}/approve/', {
        "approval_token": approval_token
    }, format='json')
    assert approve_res.status_code == 200
    assert approve_res.data["booking"]["status"] == "CONFIRMED"
    assert approve_res.data["booking"]["provider_reference"] != ""
    assert approve_res.data["pnr"] != ""

