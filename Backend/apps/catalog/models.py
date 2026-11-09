import uuid
from django.db import models
from django.utils import timezone

class Airport(models.Model):
    """Global airport catalog for IATA resolution."""
    iata_code = models.CharField(max_length=3, unique=True, primary_key=True)  # e.g. 'JFK', 'NRT', 'LHR'
    name = models.CharField(max_length=200)
    city_name = models.CharField(max_length=100)
    country_code = models.CharField(max_length=2)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    class Meta:
        ordering = ['iata_code']
        verbose_name = 'Airport'
        verbose_name_plural = 'Airports'

    def __str__(self):
        return f"{self.iata_code} - {self.name} ({self.city_name})"


class MasterHotel(models.Model):
    """Centralized Hotel Catalog de-duplicated across providers."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    neighborhood = models.CharField(max_length=100, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    star_rating = models.DecimalField(max_digits=2, decimal_places=1, default=4.0)
    review_score = models.DecimalField(max_digits=3, decimal_places=1, default=8.5)
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    currency = models.CharField(max_length=3, default="USD")
    amadeus_hotel_id = models.CharField(max_length=50, blank=True, db_index=True)
    booking_hotel_id = models.CharField(max_length=50, blank=True, db_index=True)
    address = models.TextField(blank=True)
    photo_url = models.URLField(max_length=500, blank=True)
    amenities = models.JSONField(default=list, blank=True)
    affiliate_booking_url = models.URLField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-star_rating', '-review_score']
        verbose_name = 'Master Hotel'
        verbose_name_plural = 'Master Hotels'

    def __str__(self):
        return f"{self.name} ({self.city})"


class FlightOffer(models.Model):
    """Normalized flight offer received from Amadeus or provider."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=50, default="amadeus")
    provider_offer_id = models.CharField(max_length=255)  # Raw provider offer ID
    airline_name = models.CharField(max_length=100)
    flight_number = models.CharField(max_length=20)
    origin_airport = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name="departures")
    destination_airport = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name="arrivals")
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField()
    duration_minutes = models.IntegerField()
    stops = models.IntegerField(default=0)
    cabin_class = models.CharField(max_length=30, default="economy")

    # Round trip support
    is_round_trip = models.BooleanField(default=False)
    return_departure_time = models.DateTimeField(null=True, blank=True)
    return_arrival_time = models.DateTimeField(null=True, blank=True)
    return_flight_number = models.CharField(max_length=20, blank=True)

    # Detailed segments and raw payload
    segments_json = models.JSONField(default=list, blank=True)
    raw_amadeus_offer = models.JSONField(default=dict, blank=True)

    # Pricing breakdown
    base_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")

    # Baggage & Rules
    cabin_bags = models.IntegerField(default=1)
    checked_bags = models.IntegerField(default=1)
    is_refundable = models.BooleanField(default=False)

    # Freshness
    fetched_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()  # 20 minutes from fetch
    booking_url = models.URLField(max_length=500, blank=True)

    class Meta:
        ordering = ['total_amount']
        verbose_name = 'Flight Offer'
        verbose_name_plural = 'Flight Offers'

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.airline_name} {self.flight_number} ({self.origin_airport_id} -> {self.destination_airport_id}) - {self.currency} {self.total_amount}"

