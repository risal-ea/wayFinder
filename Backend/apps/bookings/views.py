import uuid
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.bookings.models import BookingRecord
from apps.bookings.serializers import BookingRecordSerializer, BookingCreateSerializer
from apps.bookings.state_machine import BookingStateMachine, InvalidStateTransitionError

class BookingViewSet(viewsets.ModelViewSet):
    """
    Manages booking records through the auditable Finite State Machine.
    """
    queryset = BookingRecord.objects.all().select_related('trip', 'flight_offer', 'hotel')

    def get_serializer_class(self):
        if self.action == 'create':
            return BookingCreateSerializer
        return BookingRecordSerializer

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
            pnr = f"PNR-{uuid.uuid4().hex[:8].upper()}"
            fsm.confirm(provider_reference=pnr)
            return Response({
                "message": "Booking successfully authorized and confirmed!",
                "pnr": pnr,
                "booking": BookingRecordSerializer(booking).data
            }, status=status.HTTP_200_OK)
        except (PermissionError, InvalidStateTransitionError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

