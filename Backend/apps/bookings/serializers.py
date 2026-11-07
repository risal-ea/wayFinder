from rest_framework import serializers
from apps.bookings.models import BookingRecord
from apps.trips.serializers import FlightOfferSerializer, MasterHotelSerializer

class BookingRecordSerializer(serializers.ModelSerializer):
    flight_offer = FlightOfferSerializer(read_only=True)
    hotel = MasterHotelSerializer(read_only=True)

    class Meta:
        model = BookingRecord
        fields = [
            'id', 'trip', 'status', 'idempotency_key', 'item_type', 'provider',
            'flight_offer', 'hotel', 'total_amount', 'currency', 'provider_reference',
            'approval_token', 'approved_by_user', 'failure_reason', 'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'idempotency_key', 'approved_by_user', 'failure_reason']


class BookingCreateSerializer(serializers.ModelSerializer):
    flight_offer_id = serializers.UUIDField(required=False, allow_null=True)
    hotel_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = BookingRecord
        fields = [
            'id', 'trip', 'item_type', 'provider', 'flight_offer_id', 'hotel_id',
            'total_amount', 'currency'
        ]

