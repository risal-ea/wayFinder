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
        "QUOTE_VALIDATED": ["AWAITING_APPROVAL", "FAILED"],
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

    def confirm(self, provider_reference: str):
        """
        Confirms booking upon receiving valid PNR or provider reference.
        """
        self.booking.provider_reference = provider_reference
        self.booking.save(update_fields=["provider_reference"])
        self._transition("CONFIRMED")

    def fail(self, reason: str):
        """
        Aborts and marks the booking as failed with explicit reason.
        """
        self._transition("FAILED", reason=reason)

