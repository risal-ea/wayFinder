import urllib.parse
from django.conf import settings

class BookingAffiliateService:
    """
    Builds monetized deep-links to Booking.com with your affiliate tracking ID (aid).
    """

    DEFAULT_BASE_URL = "https://www.booking.com"

    def __init__(self, affiliate_id: str = None):
        self.affiliate_id = affiliate_id or getattr(settings, "BOOKING_AFFILIATE_ID", "wayfinder_aff_01")

    def build_hotel_deep_link(
        self,
        hotel_name: str,
        city: str,
        check_in_date: str = "",
        check_out_date: str = "",
        guests: int = 1,
        label: str = "wayfinder_ai"
    ) -> str:
        """
        Creates a tracking link pre-filled with destination, hotel name, and dates.
        """
        search_query = f"{hotel_name}, {city}"
        params = {
            "ss": search_query,
            "aid": self.affiliate_id,
            "label": label,
            "group_adults": str(guests),
            "no_rooms": "1",
            "group_children": "0",
        }
        if check_in_date:
            params["checkin"] = check_in_date
        if check_out_date:
            params["checkout"] = check_out_date

        query_string = urllib.parse.urlencode(params)
        return f"{self.DEFAULT_BASE_URL}/searchresults.html?{query_string}"

    def build_city_deep_link(
        self,
        city: str,
        check_in_date: str = "",
        check_out_date: str = "",
        guests: int = 1,
        label: str = "wayfinder_city_search"
    ) -> str:
        """
        Creates a city-level accommodation affiliate link.
        """
        params = {
            "ss": city,
            "aid": self.affiliate_id,
            "label": label,
            "group_adults": str(guests),
        }
        if check_in_date:
            params["checkin"] = check_in_date
        if check_out_date:
            params["checkout"] = check_out_date

        query_string = urllib.parse.urlencode(params)
        return f"{self.DEFAULT_BASE_URL}/searchresults.html?{query_string}"

