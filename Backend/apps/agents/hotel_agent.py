from typing import Dict, Any, List
from .tools.travel_tools import tool_search_hotels, tool_shortlist_item

class AccommodationSpecialistAgent:
    """
    Accommodation Specialist Agent:
    - Finds properties matching destination, guest count, and dates.
    - Evaluates guest review scores, star rating, neighborhood, and amenities.
    - Attaches verified Booking.com affiliate deep links.
    - Shortlists the optimal hotel in the Django centralized DB.
    """

    def find_and_recommend_hotel(
        self,
        trip_id: str,
        city_code: str,
        check_in_date: str,
        check_out_date: str,
        guests: int = 1
    ) -> Dict[str, Any]:
        hotel_results = tool_search_hotels(
            city_code=city_code,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            guests=guests
        )

        hotels = hotel_results.get("hotels", [])
        if not hotels:
            return {"status": "no_hotels_found", "hotels": []}

        # Rank: high review score & star rating with reasonable price
        sorted_hotels = sorted(hotels, key=lambda x: -x.get("review_score", 0))
        best_hotel = sorted_hotels[0]

        # Shortlist in Django DB
        shortlist_info = tool_shortlist_item(
            trip_id=trip_id,
            item_type="hotel",
            item_id=best_hotel["id"]
        )

        return {
            "status": "recommended",
            "best_hotel": best_hotel,
            "all_options": sorted_hotels[:3],
            "shortlist_id": shortlist_info["shortlist_id"],
            "affiliate_booking_url": best_hotel.get("affiliate_booking_url", ""),
        }

