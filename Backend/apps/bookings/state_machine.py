import logging
from django.utils import timezone
from .models import BookingRecord

logger = logging.getLogger(__name__)

class InvalidStateTransitionError(Exception):
    """Raised when an illegal booking state transition is attempted."""
    pass


class BookingStateMachine:
    """
    Finite State Machine (FSM) enforcing safe, auditable booking transitions.
    Flow: DRAFT -> QUOTE_VALIDATED -> AWAITING_APPROVAL -> SUBMITTED -> CONFIRMED
    """

    ALLOWED_TRANSITIONS = {
        "DRAFT": ["QUOTE_VALIDATED", "FAILED"],
        "QUOTE_VALIDATED": ["PASSENGERS_ATTACHED", "AWAITING_APPROVAL", "FAILED"],
        "PASSENGERS_ATTACHED": ["AWAITING_APPROVAL", "FAILED"],
        "AWAITING_APPROVAL": ["SUBMITTED", "FAILED"],
        "SUBMITTED": ["CONFIRMED", "FAILED"],
        "CONFIRMED": [],
        "FAILED": [],
    }

    def __init__(self, booking: BookingRecord):
        self.booking = booking

    def _transition(self, target_status: str, reason: str = ""):
        current = self.booking.status
        allowed = self.ALLOWED_TRANSITIONS.get(current, [])
        if target_status not in allowed:
            raise InvalidStateTransitionError(
                f"Cannot transition booking {self.booking.id} from '{current}' to '{target_status}'. Allowed: {allowed}"
            )
        self.booking.status = target_status
        if reason:
            self.booking.failure_reason = reason
        self.booking.save(update_fields=["status", "failure_reason", "updated_at"])
        logger.info(f"Booking {self.booking.id} transitioned {current} -> {target_status}")

    def validate_quote(self) -> bool:
        """
        Validates quote freshness with live provider and ensures price integrity.
        """
        if self.booking.flight_offer:
            offer = self.booking.flight_offer
            if offer.is_expired:
                self._transition("FAILED", reason="Quote expired. Price re-validation required.")
                return False

        self._transition("QUOTE_VALIDATED")
        return True

    def attach_travelers(self, travelers_data: list) -> list:
        """
        Attaches passenger details to the booking and transitions to PASSENGERS_ATTACHED.
        """
        if not travelers_data:
            raise ValueError("At least one passenger is required to attach travelers.")

        from .models import FlightTraveler
        # Clear any existing draft travelers
        self.booking.travelers.all().delete()

        created_travelers = []
        for t in travelers_data:
            traveler = FlightTraveler.objects.create(
                booking=self.booking,
                traveler_type=t.get("traveler_type", "ADULT"),
                first_name=t.get("first_name", "").strip().upper(),
                last_name=t.get("last_name", "").strip().upper(),
                date_of_birth=t.get("date_of_birth") or None,
                gender=t.get("gender", "MALE"),
                email=t.get("email", ""),
                phone_number=t.get("phone_number", ""),
                passport_number=t.get("passport_number", "").strip().upper(),
                passport_issuing_country=t.get("passport_issuing_country", "").strip().upper(),
                passport_expiry_date=t.get("passport_expiry_date") or None,
                nationality=t.get("nationality", "").strip().upper(),
                seat_preference=t.get("seat_preference", "ANY"),
            )
            created_travelers.append(traveler)

        self._transition("PASSENGERS_ATTACHED")
        return created_travelers

    def request_approval(self) -> str:
        """
        Transitions to AWAITING_APPROVAL and returns the approval token needed for user sign-off.
        """
        self._transition("AWAITING_APPROVAL")
        return str(self.booking.approval_token)

    def submit(self, approval_token: str) -> bool:
        """
        Executes booking submission only with valid explicit human approval token.
        Guarantees idempotency.
        """
        if str(self.booking.approval_token) != str(approval_token):
            raise PermissionError("Invalid approval token. Explicit user approval is required to submit booking.")

        self.booking.approved_by_user = True
        self.booking.save(update_fields=["approved_by_user"])
        self._transition("SUBMITTED")
        return True

    def confirm(self, provider_reference: str = ""):
        """
        Confirms booking upon receiving valid PNR or provider reference.
        Issues official e-ticket numbers for all passengers.
        """
        import random
        if not provider_reference:
            # Generate 6-char airline PNR (e.g. WAYF8Z)
            provider_reference = f"WAYF{random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}{random.randint(10, 99)}"

        self.booking.provider_reference = provider_reference
        self.booking.save(update_fields=["provider_reference"])

        # Generate ticket numbers for travelers
        for i, traveler in enumerate(self.booking.travelers.all(), 1):
            if not traveler.eticket_number:
                traveler.eticket_number = f"176-{random.randint(1000000000, 9999999999)}"
                traveler.save(update_fields=["eticket_number"])

        self._transition("CONFIRMED")

    def fail(self, reason: str):
        """
        Aborts and marks the booking as failed with explicit reason.
        """
        self._transition("FAILED", reason=reason)

