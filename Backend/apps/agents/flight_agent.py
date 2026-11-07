from typing import Dict, Any, List
from .tools.travel_tools import tool_search_flights, tool_shortlist_item

class FlightSpecialistAgent:
    """
    Flight Specialist Agent:
    - Finds flights matching schedule and passenger requirements.
    - Evaluates duration, stops, airline reputation, and cost.
    - Shortlists the optimal recommendation for the trip.
    """

    def find_and_recommend_flight(
        self,
        trip_id: str,
        origin: str,
        destination: str,
        departure_date: str,
        passengers: int = 1,
        cabin_class: str = "economy"
    ) -> Dict[str, Any]:
        flight_results = tool_search_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            passengers=passengers,
            cabin_class=cabin_class
        )

        offers = flight_results.get("offers", [])
        if not offers:
            return {"status": "no_flights_found", "offers": []}

        # Rank: non-stop first, then sorted by price
        sorted_offers = sorted(offers, key=lambda x: (x.get("stops", 0), x.get("total_amount", 99999)))
        best_offer = sorted_offers[0]

        # Shortlist in Django DB
        shortlist_info = tool_shortlist_item(
            trip_id=trip_id,
            item_type="flight",
            item_id=best_offer["id"]
        )

        return {
            "status": "recommended",
            "best_flight": best_offer,
            "all_options": sorted_offers[:3],
            "shortlist_id": shortlist_info["shortlist_id"],
        }

