import uuid
from django.db import models
from apps.trips.models import Trip
from apps.catalog.models import FlightOffer, MasterHotel

class BookingRecord(models.Model):
    """Auditable state machine for bookings with strict idempotency."""
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("QUOTE_VALIDATED", "Quote Validated"),
        ("AWAITING_APPROVAL", "Awaiting User Approval"),
        ("SUBMITTED", "Submitted"),
        ("CONFIRMED", "Confirmed"),
        ("FAILED", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="bookings")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="DRAFT", db_index=True)
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    item_type = models.CharField(max_length=20)  # 'flight' or 'hotel'
    provider = models.CharField(max_length=50, default="amadeus")

    flight_offer = models.ForeignKey(FlightOffer, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookings")
    hotel = models.ForeignKey(MasterHotel, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookings")

    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    provider_reference = models.CharField(max_length=100, blank=True)  # PNR or external booking reference
    
    approval_token = models.UUIDField(default=uuid.uuid4, help_text="Token required for user confirmation")
    approved_by_user = models.BooleanField(default=False)
    failure_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Booking {self.id} [{self.status}] - {self.item_type} ({self.currency} {self.total_amount})"

