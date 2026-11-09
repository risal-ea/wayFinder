from typing import Dict, Any, List, Optional
from .tools.travel_tools import (
    tool_search_flights,
    tool_get_flight_details,
    tool_revalidate_flight_price,
    tool_create_flight_booking,
    tool_approve_and_ticket_flight,
    tool_shortlist_item,
)

class FlightSpecialistAgent:
    """
    Flight Specialist Agent:
    - Specializes 100% in flight search, fare analysis, baggage policies, and booking workflows.
    - Evaluates duration, stops, airline reliability, aircraft types, and pricing.
    - Guides the user through safe human-in-the-loop flight ticketing.
    """

    def search_and_rank_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        passengers: int = 1,
        cabin_class: str = "economy",
        direct_only: bool = False
    ) -> Dict[str, Any]:
        """
        Searches flights and categorizes results into Best Overall, Cheapest, and Fastest.
        """
        results = tool_search_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            passengers=passengers,
            cabin_class=cabin_class
        )
        offers = results.get("offers", [])
        if not offers:
            return {"status": "no_flights_found", "offers": [], "summary": "No flight options found for the specified route and dates."}

        if direct_only:
            offers = [o for o in offers if o.get("stops", 0) == 0] or offers

        cheapest = min(offers, key=lambda x: x["total_amount"])
        fastest = min(offers, key=lambda x: x["duration_minutes"])
        
        # Best overall: prioritize direct flights, then balanced price & duration
        best_overall = sorted(
            offers,
            key=lambda x: (x.get("stops", 0) * 500 + x["total_amount"] + x["duration_minutes"] * 0.2)
        )[0]

        summary = (
            f"Found {len(offers)} flight option(s) for {origin} -> {destination} "
            f"({'Round-trip' if return_date else 'One-way'}, {cabin_class.title()}).\n"
            f"• **Best Overall:** {best_overall['airline']} {best_overall['flight_number']} (${best_overall['total_amount']:,.2f}, {best_overall['stops']} stops)\n"
            f"• **Cheapest:** {cheapest['airline']} {cheapest['flight_number']} (${cheapest['total_amount']:,.2f})\n"
            f"• **Fastest:** {fastest['airline']} {fastest['flight_number']} ({fastest['duration_minutes'] // 60}h {fastest['duration_minutes'] % 60}m)"
        )

        return {
            "status": "success",
            "summary": summary,
            "origin": origin,
            "destination": destination,
            "is_round_trip": bool(return_date),
            "best_overall": best_overall,
            "cheapest": cheapest,
            "fastest": fastest,
            "all_offers": offers,
        }

    def find_and_recommend_flight(
        self,
        trip_id: str,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        passengers: int = 1,
        cabin_class: str = "economy"
    ) -> Dict[str, Any]:
        """
        Finds the top flight for a trip and automatically shortlists it in the database.
        """
        ranked = self.search_and_rank_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            passengers=passengers,
            cabin_class=cabin_class
        )
        if ranked["status"] == "no_flights_found":
            return ranked

        best_flight = ranked["best_overall"]

        # Shortlist in Django DB if trip_id provided
        shortlist_id = None
        if trip_id:
            shortlist_info = tool_shortlist_item(
                trip_id=trip_id,
                item_type="flight",
                item_id=best_flight["id"]
            )
            shortlist_id = shortlist_info["shortlist_id"]

        return {
            "status": "recommended",
            "best_flight": best_flight,
            "all_options": ranked["all_offers"][:5],
            "shortlist_id": shortlist_id,
            "summary": ranked["summary"],
        }

    def initiate_flight_booking(
        self,
        offer_id: str,
        travelers: List[Dict[str, Any]],
        trip_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validates live quote with provider, attaches passenger info, and creates draft booking.
        """
        # 1. Re-validate price
        price_check = tool_revalidate_flight_price(offer_id)
        if not price_check.get("is_valid", False):
            return {"status": "error", "message": price_check.get("message", "Price validation failed.")}

        # 2. Create draft booking with travelers
        booking_result = tool_create_flight_booking(
            offer_id=offer_id,
            travelers=travelers,
            trip_id=trip_id
        )

        return {
            "status": "AWAITING_APPROVAL",
            "message": "Flight quote re-validated and passenger details attached. Ready for user confirmation.",
            **booking_result
        }

    def confirm_and_ticket_flight(self, booking_id: str, approval_token: str) -> Dict[str, Any]:
        """
        Executes explicit human sign-off and tickets the flight.
        """
        return tool_approve_and_ticket_flight(booking_id=booking_id, approval_token=approval_token)
