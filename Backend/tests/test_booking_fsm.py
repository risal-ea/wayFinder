import datetime
from decimal import Decimal
import pytest
from django.utils import timezone
from apps.catalog.models import Airport, FlightOffer
from apps.trips.models import Trip
from apps.bookings.models import BookingRecord
from apps.bookings.state_machine import BookingStateMachine, InvalidStateTransitionError

@pytest.mark.django_db
def test_booking_fsm_success_flow():
    jfk = Airport.objects.create(iata_code="JFK", name="JFK", city_name="New York", country_code="US", latitude=Decimal("40.64"), longitude=Decimal("-73.77"))
    nrt = Airport.objects.create(iata_code="NRT", name="NRT", city_name="Tokyo", country_code="JP", latitude=Decimal("35.77"), longitude=Decimal("140.39"))
    
    trip = Trip.objects.create(
        title="Tokyo Test",
        origin_city="JFK",
        destination_city="Tokyo",
        start_date=datetime.date(2026, 5, 1),
        end_date=datetime.date(2026, 5, 6),
        budget_ceiling=Decimal("3000.00")
    )

    now = timezone.now()
    flight = FlightOffer.objects.create(
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

    booking = BookingRecord.objects.create(
        trip=trip,
        item_type="flight",
        provider="amadeus",
        flight_offer=flight,
        total_amount=flight.total_amount,
        currency="USD"
    )

    fsm = BookingStateMachine(booking)
    assert booking.status == "DRAFT"

    # Step 1: Validate Quote
    valid = fsm.validate_quote()
    assert valid is True
    assert booking.status == "QUOTE_VALIDATED"

    # Step 2: Request user approval
    token = fsm.request_approval()
    assert booking.status == "AWAITING_APPROVAL"
    assert token is not None

    # Step 3: Reject submission without proper token
    with pytest.raises(PermissionError):
        fsm.submit("wrong-token-abc")

    # Step 4: Submit with valid approval token
    fsm.submit(token)
    assert booking.status == "SUBMITTED"
    assert booking.approved_by_user is True

    # Step 5: Confirm booking
    fsm.confirm("PNR-TEST1234")
    assert booking.status == "CONFIRMED"
    assert booking.provider_reference == "PNR-TEST1234"

    # Step 6: Illegal transition from CONFIRMED should fail
    with pytest.raises(InvalidStateTransitionError):
        fsm.validate_quote()

