import uuid
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from apps.catalog.models import FlightOffer, MasterHotel
from apps.bookings.models import BookingRecord
from apps.bookings.serializers import BookingRecordSerializer, BookingCreateSerializer
from apps.bookings.state_machine import BookingStateMachine, InvalidStateTransitionError

class BookingViewSet(viewsets.ModelViewSet):
    """
    Manages booking records through the auditable Finite State Machine.
    """
    queryset = BookingRecord.objects.all().select_related('trip', 'flight_offer', 'hotel').prefetch_related('travelers')

    def get_serializer_class(self):
        if self.action == 'create':
            return BookingCreateSerializer
        return BookingRecordSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        flight_offer = None
        hotel = None
        flight_offer_id = validated_data.pop('flight_offer_id', None)
        hotel_id = validated_data.pop('hotel_id', None)
        travelers_data = validated_data.pop('travelers', [])

        if flight_offer_id:
            flight_offer = get_object_or_404(FlightOffer, pk=flight_offer_id)
        if hotel_id:
            hotel = get_object_or_404(MasterHotel, pk=hotel_id)

        booking = BookingRecord.objects.create(
            flight_offer=flight_offer,
            hotel=hotel,
            **validated_data
        )

        if travelers_data:
            fsm = BookingStateMachine(booking)
            fsm.attach_travelers(travelers_data)

        return Response(BookingRecordSerializer(booking).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='validate_quote')
    def validate_quote(self, request, pk=None):
        booking = self.get_object()
        fsm = BookingStateMachine(booking)
        try:
            success = fsm.validate_quote()
            return Response({
                "status": "success" if success else "failed",
                "booking": BookingRecordSerializer(booking).data
            })
        except InvalidStateTransitionError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='attach_travelers')
    def attach_travelers(self, request, pk=None):
        booking = self.get_object()
        travelers = request.data.get('travelers', [])
        if not travelers:
            return Response({"error": "travelers list is required"}, status=status.HTTP_400_BAD_REQUEST)

        fsm = BookingStateMachine(booking)
        try:
            created = fsm.attach_travelers(travelers)
            return Response({
                "message": f"Successfully attached {len(created)} passenger(s).",
                "booking": BookingRecordSerializer(booking).data
            }, status=status.HTTP_200_OK)
        except (ValueError, InvalidStateTransitionError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='request_approval')
    def request_approval(self, request, pk=None):
        booking = self.get_object()
        fsm = BookingStateMachine(booking)
        try:
            token = fsm.request_approval()
            return Response({
                "message": "Booking requires explicit human approval before purchase.",
                "approval_token": token,
                "booking": BookingRecordSerializer(booking).data
            })
        except InvalidStateTransitionError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve_and_submit(self, request, pk=None):
        booking = self.get_object()
        approval_token = request.data.get('approval_token')
        if not approval_token:
            return Response({"error": "approval_token is required"}, status=status.HTTP_400_BAD_REQUEST)

        fsm = BookingStateMachine(booking)
        try:
            fsm.submit(approval_token)
            # In sandbox mode, immediately generate a verified PNR confirmation
            pnr = f"WAYF{uuid.uuid4().hex[:4].upper()}"
            fsm.confirm(provider_reference=pnr)
            return Response({
                "message": "Flight booking successfully authorized and ticketed!",
                "pnr": pnr,
                "booking": BookingRecordSerializer(booking).data
            }, status=status.HTTP_200_OK)
        except (PermissionError, InvalidStateTransitionError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
