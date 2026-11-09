from rest_framework import serializers
from apps.bookings.models import BookingRecord, FlightTraveler
from apps.trips.serializers import FlightOfferSerializer, MasterHotelSerializer

class FlightTravelerSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlightTraveler
        fields = [
            'id', 'traveler_type', 'first_name', 'last_name', 'date_of_birth',
            'gender', 'email', 'phone_number', 'passport_number',
            'passport_issuing_country', 'passport_expiry_date', 'nationality',
            'eticket_number', 'seat_preference', 'created_at'
        ]


class BookingRecordSerializer(serializers.ModelSerializer):
    flight_offer = FlightOfferSerializer(read_only=True)
    hotel = MasterHotelSerializer(read_only=True)
    travelers = FlightTravelerSerializer(many=True, read_only=True)

    class Meta:
        model = BookingRecord
        fields = [
            'id', 'trip', 'status', 'idempotency_key', 'item_type', 'provider',
            'flight_offer', 'hotel', 'total_amount', 'currency', 'provider_reference',
            'approval_token', 'approved_by_user', 'failure_reason', 'travelers',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'idempotency_key', 'approved_by_user', 'failure_reason', 'provider_reference']


class BookingCreateSerializer(serializers.ModelSerializer):
    flight_offer_id = serializers.UUIDField(required=False, allow_null=True)
    hotel_id = serializers.UUIDField(required=False, allow_null=True)
    travelers = serializers.ListField(child=serializers.DictField(), required=False, write_only=True)

    class Meta:
        model = BookingRecord
        fields = [
            'id', 'trip', 'item_type', 'provider', 'flight_offer_id', 'hotel_id',
            'total_amount', 'currency', 'travelers'
        ]
        extra_kwargs = {
            'trip': {'required': False, 'allow_null': True}
        }
