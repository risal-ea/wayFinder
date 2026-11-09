from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from apps.catalog.models import Airport, MasterHotel, FlightOffer
from apps.catalog.services.ingestion import TravelIngestionService
from apps.trips.models import Trip, ItineraryDay, TripShortlist
from apps.trips.serializers import (
    TripDetailSerializer,
    TripCreateSerializer,
    ItineraryDaySerializer,
    TripShortlistSerializer,
    FlightOfferSerializer,
    MasterHotelSerializer,
    AirportSerializer,
)

class TripViewSet(viewsets.ModelViewSet):
    """
    CRUD API for Trip planning, daily itineraries, and shortlisted items.
    """
    queryset = Trip.objects.all().prefetch_related('days', 'shortlist_items')

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TripCreateSerializer
        return TripDetailSerializer

    @action(detail=True, methods=['post'], url_path='add_day')
    def add_day(self, request, pk=None):
        trip = self.get_object()
        serializer = ItineraryDaySerializer(data=request.data)
        if serializer.is_valid():
            day_number = serializer.validated_data['day_number']
            ItineraryDay.objects.update_or_create(
                trip=trip,
                day_number=day_number,
                defaults=serializer.validated_data
            )
            trip = Trip.objects.prefetch_related('days', 'shortlist_items').get(id=trip.id)
            return Response(TripDetailSerializer(trip).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='shortlist')
    def shortlist_item(self, request, pk=None):
        trip = self.get_object()
        item_type = request.data.get('item_type')
        item_id = request.data.get('item_id')
        notes = request.data.get('notes', '')

        if item_type not in ['flight', 'hotel']:
            return Response({"error": "item_type must be 'flight' or 'hotel'"}, status=status.HTTP_400_BAD_REQUEST)

        flight_offer = None
        hotel = None

        if item_type == 'flight':
            flight_offer = get_object_or_404(FlightOffer, pk=item_id)
        elif item_type == 'hotel':
            hotel = get_object_or_404(MasterHotel, pk=item_id)

        shortlist_item, created = TripShortlist.objects.get_or_create(
            trip=trip,
            item_type=item_type,
            flight_offer=flight_offer,
            hotel=hotel,
            defaults={"notes": notes, "is_selected_for_booking": True}
        )
        trip = Trip.objects.prefetch_related('days', 'shortlist_items').get(id=trip.id)
        return Response(TripDetailSerializer(trip).data, status=status.HTTP_201_CREATED)


class SearchFlightsAPIView(APIView):
    """
    Searches flights via active provider (Amadeus or Mock), ingests into Central DB, and returns results.
    Supports one-way and round-trip searches.
    """
    def post(self, request):
        params = request.data if request.data else request.query_params
        origin = params.get('origin')
        destination = params.get('destination')
        departure_date = params.get('departure_date')
        return_date = params.get('return_date')
        passengers = int(params.get('passengers', 1))
        cabin_class = params.get('cabin_class', 'economy')

        if not origin or not destination or not departure_date:
            return Response(
                {"error": "origin, destination, and departure_date are required fields"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            service = TravelIngestionService()
            offers = service.ingest_flights(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                passengers=passengers,
                cabin_class=cabin_class
            )
            serializer = FlightOfferSerializer(offers, many=True)
            return Response({"count": len(offers), "results": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        return self.post(request)


class SearchHotelsAPIView(APIView):
    """
    Searches hotels via active provider (Amadeus or Mock), attaches Booking.com affiliate links, and ingests into DB.
    """
    def post(self, request):
        city_code = request.data.get('city_code')
        check_in_date = request.data.get('check_in_date', '')
        check_out_date = request.data.get('check_out_date', '')
        guests = int(request.data.get('guests', 1))

        if not city_code:
            return Response({"error": "city_code is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            service = TravelIngestionService()
            hotels = service.ingest_hotels(
                city_code=city_code,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                guests=guests
            )
            serializer = MasterHotelSerializer(hotels, many=True)
            return Response({"count": len(hotels), "results": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        return self.post(request)


class AirportsListAPIView(APIView):
    """
    Lists known global airports from the centralized database.
    """
    def get(self, request):
        query = request.query_params.get('q', '').strip()
        airports = Airport.objects.all()
        if query:
            airports = airports.filter(name__icontains=query) | airports.filter(iata_code__icontains=query) | airports.filter(city_name__icontains=query)
        serializer = AirportSerializer(airports[:50], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
