from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseTravelProvider(ABC):
    """
    Abstract interface for all travel provider adapters (Amadeus, Mock, Skyscanner, etc.)
    """

    @abstractmethod
    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        passengers: int = 1,
        cabin_class: str = "economy"
    ) -> List[Dict[str, Any]]:
        """
        Search for flight offers.
        Returns a list of normalized flight offer dictionaries.
        """
        pass

    @abstractmethod
    def search_hotels(
        self,
        city_code: str,
        check_in_date: str,
        check_out_date: str,
        guests: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Search for hotel properties and offers.
        Returns a list of normalized hotel dictionaries.
        """
        pass

    @abstractmethod
    def validate_flight_price(self, raw_offer: Dict[str, Any]) -> Dict[str, Any]:
        """
        Re-validates flight price and seat availability with the live provider prior to booking.
        """
        pass

