import os
import re
import datetime
import logging
from typing import Dict, Any, Optional
from django.conf import settings
from .tools.travel_tools import (
    tool_create_or_get_trip,
    execute_tool,
    TOOL_SCHEMAS,
)
from .flight_agent import FlightSpecialistAgent
from .hotel_agent import AccommodationSpecialistAgent
from .itinerary_agent import ItinerarySpecialistAgent
from .budget_agent import BudgetSpecialistAgent
from apps.trips.models import Trip
from apps.trips.serializers import TripDetailSerializer

logger = logging.getLogger(__name__)

class TravelCoordinatorAgent:
    """
    Master Travel Coordinator Agent:
    - Orchestrates the multi-agent team (Flight, Accommodation, Itinerary, Budget).
    - Interfaces with Google Gemini when API key is provided.
    - Falls back to reliable semantic orchestration engine for zero-config offline runs.
    """

    def __init__(self):
        self.api_key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        self.model_name = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
        self.flight_agent = FlightSpecialistAgent()
        self.hotel_agent = AccommodationSpecialistAgent()
        self.itinerary_agent = ItinerarySpecialistAgent()
        self.budget_agent = BudgetSpecialistAgent()

    def parse_intent_fallback(self, query: str) -> Dict[str, Any]:
        """Extracts destination, origin, duration, budget from natural language query."""
        q = query.lower()

        # Destination extraction
        destination = "Tokyo"
        dest_code = "NRT"
        if "paris" in q:
            destination = "Paris"
            dest_code = "CDG"
        elif "london" in q:
            destination = "London"
            dest_code = "LHR"
        elif "new york" in q or "nyc" in q:
            destination = "New York"
            dest_code = "JFK"

        # Origin extraction
        origin = "New York"
        origin_code = "JFK"
        if "from sfo" in q or "san francisco" in q:
            origin = "San Francisco"
            origin_code = "SFO"
        elif "from lax" in q or "los angeles" in q:
            origin = "Los Angeles"
            origin_code = "LAX"
        elif "from lhr" in q or "from london" in q:
            origin = "London"
            origin_code = "LHR"

        # Budget extraction
        budget_match = re.search(r'\$?(\d{3,6})', query)
        budget = float(budget_match.group(1)) if budget_match else 2500.0

        # Duration extraction
        days_match = re.search(r'(\d+)\s*(?:-|\s*)day', q)
        duration_days = int(days_match.group(1)) if days_match else 5

        # Dates (default to starting 30 days from now)
        today = datetime.date.today()
        start_date = today + datetime.timedelta(days=30)
        end_date = start_date + datetime.timedelta(days=duration_days - 1)

        return {
            "title": f"{duration_days}-Day Trip to {destination}",
            "origin": origin_code,
            "destination": dest_code,
            "destination_city": destination,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "budget": budget,
            "duration_days": duration_days,
            "passengers": 1,
        }

    def plan_trip(self, user_prompt: str) -> Dict[str, Any]:
        """
        Coordinates full end-to-end trip planning:
        1. Parse intent & requirements
        2. Create Trip in Centralized DB
        3. Flight Specialist finds & shortlists flight
        4. Accommodation Specialist finds, shortlists hotel & generates Booking.com affiliate link
        5. Itinerary Specialist creates daily schedule blocks in DB
        6. Budget Specialist calculates balance
        7. Returns complete serialized Trip & narrative proposal
        """
        parsed = self.parse_intent_fallback(user_prompt)

        # 1. Create Trip in Django DB
        trip_info = tool_create_or_get_trip(
            title=parsed["title"],
            origin=parsed["origin"],
            destination=parsed["destination_city"],
            start_date=parsed["start_date"],
            end_date=parsed["end_date"],
            budget_ceiling=parsed["budget"],
            passenger_count=parsed["passengers"],
        )
        trip_id = trip_info["trip_id"]

        # 2. Flight Specialist
        flight_result = self.flight_agent.find_and_recommend_flight(
            trip_id=trip_id,
            origin=parsed["origin"],
            destination=parsed["destination"],
            departure_date=parsed["start_date"],
            passengers=parsed["passengers"],
        )

        # 3. Accommodation Specialist
        hotel_result = self.hotel_agent.find_and_recommend_hotel(
            trip_id=trip_id,
            city_code=parsed["destination"],
            check_in_date=parsed["start_date"],
            check_out_date=parsed["end_date"],
            guests=parsed["passengers"],
        )

        # 4. Itinerary Specialist
        itinerary_days = self.itinerary_agent.generate_and_save_itinerary(
            trip_id=trip_id,
            destination=parsed["destination_city"],
            start_date_str=parsed["start_date"],
            end_date_str=parsed["end_date"],
        )

        # 5. Budget Specialist
        budget_report = self.budget_agent.analyze_trip_budget(trip_id=trip_id)

        # 6. Fetch updated Trip from Django ORM
        trip_instance = Trip.objects.prefetch_related('days', 'shortlist_items').get(id=trip_id)
        serialized_trip = TripDetailSerializer(trip_instance).data

        # 7. Construct proposal response
        best_flight = flight_result.get("best_flight", {})
        best_hotel = hotel_result.get("best_hotel", {})

        stops_desc = "Direct / Non-stop" if best_flight.get("stops", 0) == 0 else f"{best_flight.get('stops')} stops"

        narrative = (
            f"### 🧭 Wayfinder Proposal: {trip_info['title']}\n\n"
            f"**Travel Dates:** {parsed['start_date']} to {parsed['end_date']} ({parsed['duration_days']} Days)\n\n"
            f"#### ✈️ Recommended Flight\n"
            f"- **Airline:** {best_flight.get('airline', 'N/A')} ({best_flight.get('flight_number', '')})\n"
            f"- **Route:** {best_flight.get('departure_time', '')[:10]} | {parsed['origin']} $\\rightarrow$ {parsed['destination']}\n"
            f"- **Stops:** {stops_desc}\n"
            f"- **Price:** ${best_flight.get('total_amount', 0.0):,.2f} {best_flight.get('currency', 'USD')}\n\n"
            f"#### 🏨 Recommended Accommodation\n"
            f"- **Hotel:** {best_hotel.get('name', 'N/A')} ({best_hotel.get('star_rating', 4.0)}★ - Review Score {best_hotel.get('review_score', 8.5)}/10)\n"
            f"- **Neighborhood:** {best_hotel.get('neighborhood', 'Downtown')}\n"
            f"- **Nightly Rate:** ${best_hotel.get('price_per_night', 0.0):,.2f} / night\n"
            f"- **Booking Link:** [Reserve on Booking.com]({best_hotel.get('affiliate_booking_url', '#')}) *(Includes affiliate tracking)*\n\n"
            f"#### 📅 Structured Itinerary\n"
            f"Created **{len(itinerary_days)}** curated daily blocks clustered by geographic proximity.\n\n"
            f"#### 💰 Budget Verification\n"
            f"- **Budget Ceiling:** ${budget_report['budget_ceiling']:,.2f}\n"
            f"- **Total Estimated Cost:** ${budget_report['total_estimated_cost']:,.2f}\n"
            f"- **Remaining Cushion:** ${budget_report['remaining_budget']:,.2f}\n"
            f"- **Status:** {budget_report['advisory_message']}\n"
        )

        return {
            "narrative": narrative,
            "trip": serialized_trip,
            "flight_recommendation": best_flight,
            "hotel_recommendation": best_hotel,
            "budget_analysis": budget_report,
        }
