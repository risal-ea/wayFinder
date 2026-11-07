import datetime
from decimal import Decimal
from typing import Dict, Any, List
from apps.catalog.services.ingestion import TravelIngestionService
from apps.catalog.models import Airport, FlightOffer, MasterHotel
from apps.trips.models import Trip, ItineraryDay, TripShortlist

def tool_search_flights(origin: str, destination: str, departure_date: str, passengers: int = 1, cabin_class: str = "economy") -> Dict[str, Any]:
    """Search for flights and ingest normalized offers into Django centralized database."""
    service = TravelIngestionService()
    offers = service.ingest_flights(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        passengers=passengers,
        cabin_class=cabin_class
    )
    return {
        "count": len(offers),
        "origin": origin,
        "destination": destination,
        "offers": [
            {
                "id": str(o.id),
                "airline": o.airline_name,
                "flight_number": o.flight_number,
                "departure_time": o.departure_time.isoformat(),
                "arrival_time": o.arrival_time.isoformat(),
                "duration_minutes": o.duration_minutes,
                "stops": o.stops,
                "total_amount": float(o.total_amount),
                "currency": o.currency,
                "cabin_class": o.cabin_class,
            }
            for o in offers[:5]
        ]
    }

def tool_search_hotels(city_code: str, check_in_date: str, check_out_date: str, guests: int = 1) -> Dict[str, Any]:
    """Search for hotels and ingest into Django centralized database with Booking.com affiliate links."""
    service = TravelIngestionService()
    hotels = service.ingest_hotels(
        city_code=city_code,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        guests=guests
    )
    return {
        "count": len(hotels),
        "city_code": city_code,
        "hotels": [
            {
                "id": str(h.id),
                "name": h.name,
                "neighborhood": h.neighborhood,
                "star_rating": float(h.star_rating),
                "review_score": float(h.review_score),
                "price_per_night": float(h.price_per_night),
                "currency": h.currency,
                "amenities": h.amenities,
                "affiliate_booking_url": h.affiliate_booking_url,
            }
            for h in hotels[:5]
        ]
    }

def tool_create_or_get_trip(title: str, origin: str, destination: str, start_date: str, end_date: str, budget_ceiling: float, passenger_count: int = 1) -> Dict[str, Any]:
    """Creates or updates a Trip record in the Django centralized database."""
    s_date = datetime.date.fromisoformat(start_date)
    e_date = datetime.date.fromisoformat(end_date)
    trip, created = Trip.objects.get_or_create(
        title=title,
        destination_city=destination,
        defaults={
            "origin_city": origin,
            "start_date": s_date,
            "end_date": e_date,
            "budget_ceiling": Decimal(str(budget_ceiling)),
            "passenger_count": passenger_count,
            "currency": "USD",
            "status": "PLANNING",
        }
    )
    return {
        "trip_id": str(trip.id),
        "title": trip.title,
        "destination": trip.destination_city,
        "created": created,
        "budget_ceiling": float(trip.budget_ceiling),
        "currency": trip.currency,
    }

def tool_save_itinerary_day(trip_id: str, day_number: int, date: str, theme: str, activities: List[Dict[str, Any]], day_cost: float = 0.0) -> Dict[str, Any]:
    """Saves a daily itinerary block into the Django database."""
    trip = Trip.objects.get(id=trip_id)
    day_date = datetime.date.fromisoformat(date)
    itinerary_day, created = ItineraryDay.objects.update_or_create(
        trip=trip,
        day_number=day_number,
        defaults={
            "date": day_date,
            "theme": theme,
            "activities_json": activities,
            "day_cost_estimate": Decimal(str(day_cost)),
        }
    )
    trip.status = "ITINERARY_GENERATED"
    trip.save(update_fields=["status"])
    return {
        "itinerary_day_id": str(itinerary_day.id),
        "day_number": day_number,
        "theme": theme,
        "activity_count": len(activities),
        "day_cost_estimate": float(itinerary_day.day_cost_estimate),
    }

def tool_shortlist_item(trip_id: str, item_type: str, item_id: str) -> Dict[str, Any]:
    """Attaches a chosen flight offer or hotel to the trip shortlist."""
    trip = Trip.objects.get(id=trip_id)
    flight = None
    hotel = None
    if item_type == "flight":
        flight = FlightOffer.objects.get(id=item_id)
    elif item_type == "hotel":
        hotel = MasterHotel.objects.get(id=item_id)
    else:
        raise ValueError("item_type must be flight or hotel")

    shortlist, created = TripShortlist.objects.get_or_create(
        trip=trip,
        item_type=item_type,
        flight_offer=flight,
        hotel=hotel,
        defaults={"is_selected_for_booking": True}
    )
    return {
        "shortlist_id": str(shortlist.id),
        "item_type": item_type,
        "trip_id": str(trip.id),
        "created": created,
    }

def tool_calculate_trip_budget(trip_id: str) -> Dict[str, Any]:
    """Calculates total estimated cost, remaining balance, and budget safety."""
    trip = Trip.objects.get(id=trip_id)
    ceiling = float(trip.budget_ceiling)
    total_est = float(trip.total_estimated_cost)
    balance = ceiling - total_est
    return {
        "trip_id": str(trip.id),
        "budget_ceiling": ceiling,
        "total_estimated_cost": total_est,
        "remaining_budget": balance,
        "currency": trip.currency,
        "within_budget": balance >= 0,
    }

# Tool Dispatcher
TOOL_REGISTRY = {
    "tool_search_flights": tool_search_flights,
    "tool_search_hotels": tool_search_hotels,
    "tool_create_or_get_trip": tool_create_or_get_trip,
    "tool_save_itinerary_day": tool_save_itinerary_day,
    "tool_shortlist_item": tool_shortlist_item,
    "tool_calculate_trip_budget": tool_calculate_trip_budget,
}

TOOL_SCHEMAS = [
    {
        "name": "tool_search_flights",
        "description": "Searches for flights between origin and destination on a given date and returns normalized offers.",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "3-letter IATA code, e.g. JFK"},
                "destination": {"type": "string", "description": "3-letter IATA code, e.g. NRT"},
                "departure_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "passengers": {"type": "integer", "description": "Number of passengers"},
                "cabin_class": {"type": "string", "enum": ["economy", "business", "first"]},
            },
            "required": ["origin", "destination", "departure_date"]
        }
    },
    {
        "name": "tool_search_hotels",
        "description": "Searches for hotels in a destination city and returns properties with Booking.com affiliate booking links.",
        "parameters": {
            "type": "object",
            "properties": {
                "city_code": {"type": "string", "description": "City code or IATA, e.g. TYO, PAR"},
                "check_in_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "check_out_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "guests": {"type": "integer", "description": "Number of guests"},
            },
            "required": ["city_code", "check_in_date", "check_out_date"]
        }
    },
    {
        "name": "tool_create_or_get_trip",
        "description": "Creates or retrieves a Trip record in the Django centralized database.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title of trip, e.g. '5-Day Tokyo Adventure'"},
                "origin": {"type": "string", "description": "Origin city or airport code"},
                "destination": {"type": "string", "description": "Destination city or airport code"},
                "start_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "budget_ceiling": {"type": "number", "description": "Maximum budget ceiling in USD"},
                "passenger_count": {"type": "integer", "description": "Number of travelers"},
            },
            "required": ["title", "origin", "destination", "start_date", "end_date", "budget_ceiling"]
        }
    },
    {
        "name": "tool_save_itinerary_day",
        "description": "Saves a detailed daily itinerary block with activities into the database.",
        "parameters": {
            "type": "object",
            "properties": {
                "trip_id": {"type": "string", "description": "UUID of the Trip"},
                "day_number": {"type": "integer", "description": "Day index (1, 2, ...)"},
                "date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "theme": {"type": "string", "description": "Theme of the day"},
                "activities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "time_of_day": {"type": "string", "enum": ["morning", "afternoon", "evening"]},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "location": {"type": "string"},
                            "estimated_cost": {"type": "number"},
                        },
                        "required": ["time_of_day", "title", "location"]
                    }
                },
                "day_cost": {"type": "number", "description": "Total estimated cost for this day"}
            },
            "required": ["trip_id", "day_number", "date", "theme", "activities"]
        }
    },
    {
        "name": "tool_shortlist_item",
        "description": "Shortlists a specific flight offer or hotel property for the trip proposal.",
        "parameters": {
            "type": "object",
            "properties": {
                "trip_id": {"type": "string", "description": "UUID of the Trip"},
                "item_type": {"type": "string", "enum": ["flight", "hotel"]},
                "item_id": {"type": "string", "description": "UUID of FlightOffer or MasterHotel"},
            },
            "required": ["trip_id", "item_type", "item_id"]
        }
    },
    {
        "name": "tool_calculate_trip_budget",
        "description": "Calculates the total cost and remaining budget balance for a trip.",
        "parameters": {
            "type": "object",
            "properties": {
                "trip_id": {"type": "string", "description": "UUID of the Trip"}
            },
            "required": ["trip_id"]
        }
    }
]

def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Executes a registered tool by name with provided arguments."""
    func = TOOL_REGISTRY.get(tool_name)
    if not func:
        raise ValueError(f"Unknown tool: {tool_name}")
    return func(**arguments)

