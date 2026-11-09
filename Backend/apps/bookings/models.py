import uuid
from django.db import models
from apps.trips.models import Trip
from apps.catalog.models import FlightOffer, MasterHotel

class BookingRecord(models.Model):
    """Auditable state machine for bookings with strict idempotency."""
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("QUOTE_VALIDATED", "Quote Validated"),
        ("PASSENGERS_ATTACHED", "Passengers Attached"),
        ("AWAITING_APPROVAL", "Awaiting User Approval"),
        ("SUBMITTED", "Submitted"),
        ("CONFIRMED", "Confirmed"),
        ("FAILED", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="bookings", null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="DRAFT", db_index=True)
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    item_type = models.CharField(max_length=20, default="flight")  # 'flight' or 'hotel'
    provider = models.CharField(max_length=50, default="amadeus")

    flight_offer = models.ForeignKey(FlightOffer, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookings")
    hotel = models.ForeignKey(MasterHotel, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookings")

    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    provider_reference = models.CharField(max_length=100, blank=True)  # PNR or airline confirmation code
    
    approval_token = models.UUIDField(default=uuid.uuid4, help_text="Token required for user confirmation")
    approved_by_user = models.BooleanField(default=False)
    failure_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        pnr_display = f" [PNR: {self.provider_reference}]" if self.provider_reference else ""
        return f"Booking {self.id} [{self.status}]{pnr_display} - {self.item_type} ({self.currency} {self.total_amount})"


class FlightTraveler(models.Model):
    """Passenger attached to an auditable flight booking."""
    TRAVELER_TYPES = [
        ("ADULT", "Adult (12+)"),
        ("CHILD", "Child (2-11)"),
        ("INFANT", "Infant (under 2)"),
    ]
    GENDER_CHOICES = [
        ("MALE", "Male"),
        ("FEMALE", "Female"),
        ("OTHER", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(BookingRecord, on_delete=models.CASCADE, related_name="travelers")
    traveler_type = models.CharField(max_length=10, choices=TRAVELER_TYPES, default="ADULT")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default="MALE")
    email = models.EmailField(blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    
    # Document / Passport
    passport_number = models.CharField(max_length=50, blank=True)
    passport_issuing_country = models.CharField(max_length=3, blank=True)
    passport_expiry_date = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=3, blank=True)
    
    # Ticketing info
    eticket_number = models.CharField(max_length=50, blank=True)
    seat_preference = models.CharField(max_length=20, default="ANY")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.traveler_type}) - Ticket: {self.eticket_number or 'PENDING'}"

