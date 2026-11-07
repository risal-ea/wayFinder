from rest_framework import serializers
from apps.catalog.models import Airport, MasterHotel, FlightOffer
from apps.trips.models import Trip, ItineraryDay, TripShortlist

class AirportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airport
        fields = ['iata_code', 'name', 'city_name', 'country_code', 'latitude', 'longitude']


class FlightOfferSerializer(serializers.ModelSerializer):
    origin_airport = AirportSerializer(read_only=True)
    destination_airport = AirportSerializer(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = FlightOffer
        fields = [
            'id', 'provider', 'provider_offer_id', 'airline_name', 'flight_number',
            'origin_airport', 'destination_airport', 'departure_time', 'arrival_time',
            'duration_minutes', 'stops', 'cabin_class', 'total_amount', 'currency',
            'cabin_bags', 'checked_bags', 'is_refundable', 'fetched_at', 'expires_at',
            'is_expired', 'booking_url'
        ]


class MasterHotelSerializer(serializers.ModelSerializer):
    class Meta:
        model = MasterHotel
        fields = [
            'id', 'name', 'city', 'neighborhood', 'latitude', 'longitude',
            'star_rating', 'review_score', 'price_per_night', 'currency',
            'amadeus_hotel_id', 'booking_hotel_id', 'address', 'photo_url',
            'amenities', 'affiliate_booking_url'
        ]


class ItineraryDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = ItineraryDay
        fields = ['id', 'day_number', 'date', 'theme', 'activities_json', 'day_cost_estimate']


class TripShortlistSerializer(serializers.ModelSerializer):
    flight_offer = FlightOfferSerializer(read_only=True)
    hotel = MasterHotelSerializer(read_only=True)
    flight_offer_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    hotel_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = TripShortlist
        fields = [
            'id', 'item_type', 'flight_offer', 'hotel', 'flight_offer_id',
            'hotel_id', 'is_selected_for_booking', 'notes', 'created_at'
        ]


class TripDetailSerializer(serializers.ModelSerializer):
    days = ItineraryDaySerializer(many=True, read_only=True)
    shortlist_items = TripShortlistSerializer(many=True, read_only=True)
    total_estimated_cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Trip
        fields = [
            'id', 'title', 'origin_city', 'destination_city', 'start_date', 'end_date',
            'passenger_count', 'budget_ceiling', 'currency', 'status',
            'total_estimated_cost', 'days', 'shortlist_items', 'created_at', 'updated_at'
        ]


class TripCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = [
            'id', 'title', 'origin_city', 'destination_city', 'start_date', 'end_date',
            'passenger_count', 'budget_ceiling', 'currency', 'status'
        ]

