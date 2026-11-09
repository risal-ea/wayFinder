from django.contrib import admin
from .models import Airport, MasterHotel, FlightOffer

@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    list_display = ('iata_code', 'name', 'city_name', 'country_code', 'latitude', 'longitude')
    search_fields = ('iata_code', 'name', 'city_name')
    list_filter = ('country_code',)

@admin.register(MasterHotel)
class MasterHotelAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'star_rating', 'review_score', 'price_per_night', 'currency', 'amadeus_hotel_id')
    search_fields = ('name', 'city', 'neighborhood', 'amadeus_hotel_id')
    list_filter = ('city', 'star_rating')
    readonly_fields = ('id', 'created_at', 'updated_at')

@admin.register(FlightOffer)
class FlightOfferAdmin(admin.ModelAdmin):
    list_display = ('airline_name', 'flight_number', 'origin_airport', 'destination_airport', 'departure_time', 'is_round_trip', 'stops', 'total_amount', 'currency', 'is_refundable', 'expires_at')
    search_fields = ('airline_name', 'flight_number', 'origin_airport__iata_code', 'destination_airport__iata_code')
    list_filter = ('airline_name', 'cabin_class', 'stops', 'is_round_trip', 'is_refundable', 'currency')
    readonly_fields = ('id', 'fetched_at')

