import uuid
import datetime
from typing import List, Dict, Any, Optional
from apps.providers.base import BaseTravelProvider
from apps.providers.affiliate import BookingAffiliateService

class MockTravelProvider(BaseTravelProvider):
    """
    Offline deterministic travel provider for unit tests, local staging, and zero-API-cost development.
    """

    AIRLINE_MAPPINGS = {
        ("JFK", "NRT"): [
            ("All Nippon Airways", "NH009", 840, 0, 950.00),
            ("Japan Airlines", "JL005", 850, 0, 980.00),
            ("United Airlines", "UA079", 870, 0, 890.00),
            ("Air Canada", "AC009", 1020, 1, 740.00),
        ],
        ("JFK", "LHR"): [
            ("British Airways", "BA178", 420, 0, 680.00),
            ("Virgin Atlantic", "VS004", 415, 0, 690.00),
            ("Delta Air Lines", "DL002", 430, 0, 650.00),
        ],
        ("JFK", "CDG"): [
            ("Air France", "AF007", 450, 0, 720.00),
            ("Delta Air Lines", "DL264", 455, 0, 710.00),
        ],
    }

    HOTEL_CATALOG = {
        "TYO": [
            {
                "name": "Park Hyatt Tokyo",
                "city": "Tokyo",
                "neighborhood": "Shinjuku",
                "latitude": 35.6853,
                "longitude": 139.6912,
                "star_rating": 5.0,
                "review_score": 9.4,
                "price_per_night": 450.00,
                "currency": "USD",
                "address": "3-7-1-2 Nishi-Shinjuku, Shinjuku-ku, Tokyo",
                "amenities": ["Spa", "Indoor Pool", "Skyline View", "Fine Dining", "Fitness Center"],
                "amadeus_hotel_id": "TYOPHT01",
                "photo_url": "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=600",
            },
            {
                "name": "Hotel Gracery Shinjuku",
                "city": "Tokyo",
                "neighborhood": "Kabukicho",
                "latitude": 35.6954,
                "longitude": 139.7020,
                "star_rating": 4.0,
                "review_score": 8.7,
                "price_per_night": 160.00,
                "currency": "USD",
                "address": "1-19-1 Kabukicho, Shinjuku-ku, Tokyo",
                "amenities": ["Godzilla Head Terrace", "Free Wi-Fi", "Restaurant", "Subway Access"],
                "amadeus_hotel_id": "TYOHGS02",
                "photo_url": "https://images.unsplash.com/photo-1503899036084-c55cdd92da26?w=600",
            },
            {
                "name": "The Ritz-Carlton Tokyo",
                "city": "Tokyo",
                "neighborhood": "Roppongi",
                "latitude": 35.6664,
                "longitude": 139.7310,
                "star_rating": 5.0,
                "review_score": 9.3,
                "price_per_night": 620.00,
                "currency": "USD",
                "address": "Tokyo Midtown 9-7-1 Akasaka, Minato-ku, Tokyo",
                "amenities": ["Michelin-starred Dining", "Club Lounge", "Spa", "Panoramic City Views"],
                "amadeus_hotel_id": "TYORCT03",
                "photo_url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600",
            },
        ],
        "PAR": [
            {
                "name": "Le Meurice - Dorchester Collection",
                "city": "Paris",
                "neighborhood": "1st Arrondissement",
                "latitude": 48.8656,
                "longitude": 2.3292,
                "star_rating": 5.0,
                "review_score": 9.5,
                "price_per_night": 780.00,
                "currency": "USD",
                "address": "228 Rue de Rivoli, 75001 Paris",
                "amenities": ["Palace Hotel", "Valmont Spa", "Alain Ducasse Restaurant"],
                "amadeus_hotel_id": "PARLM01",
                "photo_url": "https://images.unsplash.com/photo-1549294413-26f195200c16?w=600",
            },
            {
                "name": "CitizenM Paris Gare de Lyon",
                "city": "Paris",
                "neighborhood": "12th Arrondissement",
                "latitude": 48.8449,
                "longitude": 2.3734,
                "star_rating": 4.0,
                "review_score": 8.8,
                "price_per_night": 175.00,
                "currency": "USD",
                "address": "8 Rue Van Gogh, 75012 Paris",
                "amenities": ["Rooftop Bar", "MoodPad Room Controls", "High-Speed Wi-Fi"],
                "amadeus_hotel_id": "PARCIT02",
                "photo_url": "https://images.unsplash.com/photo-1568495248636-6432b97bd949?w=600",
            },
        ],
    }

    def __init__(self):
        self.affiliate_service = BookingAffiliateService()

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        passengers: int = 1,
        cabin_class: str = "economy"
    ) -> List[Dict[str, Any]]:
        origin = origin.upper()
        destination = destination.upper()
        key = (origin, destination)

        dep_dt = datetime.datetime.fromisoformat(departure_date) if "T" in departure_date else datetime.datetime.strptime(departure_date, "%Y-%m-%d").replace(hour=10, minute=30)
        
        flights = self.AIRLINE_MAPPINGS.get(key)
        if not flights:
            # Fallback dynamic mock for any pair
            flights = [
                ("Global Airways", "GA101", 520, 0, 720.00),
                ("Sky Connect", "SC204", 640, 1, 580.00),
                ("Aero Star", "AS505", 480, 0, 810.00),
            ]

        results = []
        for i, (airline, flight_no, duration, stops, base_price) in enumerate(flights):
            offer_id = f"mock-fl-{origin}-{destination}-{i+1}"
            arr_dt = dep_dt + datetime.timedelta(minutes=duration)
            total = round(base_price * passengers * (1.8 if cabin_class == "business" else 1.0), 2)

            results.append({
                "provider": "mock",
                "provider_offer_id": offer_id,
                "airline_name": airline,
                "flight_number": flight_no,
                "origin_iata": origin,
                "destination_iata": destination,
                "departure_time": dep_dt.isoformat(),
                "arrival_time": arr_dt.isoformat(),
                "duration_minutes": duration,
                "stops": stops,
                "cabin_class": cabin_class,
                "total_amount": total,
                "currency": "USD",
                "cabin_bags": 1,
                "checked_bags": 1 if cabin_class == "economy" else 2,
                "is_refundable": True if i == 0 else False,
                "expires_in_minutes": 20,
                "booking_url": f"https://example.com/mock-book/flight/{offer_id}",
            })

        return results

    def search_hotels(
        self,
        city_code: str,
        check_in_date: str,
        check_out_date: str,
        guests: int = 1
    ) -> List[Dict[str, Any]]:
        city_key = city_code.upper()
        # Map common IATA codes to city keys
        if city_key in ("NRT", "HND", "TOKYO"):
            city_key = "TYO"
        elif city_key in ("CDG", "ORY", "PARIS"):
            city_key = "PAR"

        hotels = self.HOTEL_CATALOG.get(city_key)
        if not hotels:
            # Generic city fallback
            hotels = [
                {
                    "name": f"Grand Central Hotel {city_code}",
                    "city": city_code,
                    "neighborhood": "City Center",
                    "latitude": 40.7128,
                    "longitude": -74.0060,
                    "star_rating": 4.5,
                    "review_score": 8.9,
                    "price_per_night": 210.00,
                    "currency": "USD",
                    "address": f"100 Main Boulevard, {city_code}",
                    "amenities": ["Breakfast Included", "Free High-Speed Wi-Fi", "Fitness Room"],
                    "amadeus_hotel_id": f"{city_code}GCH01",
                    "photo_url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600",
                },
                {
                    "name": f"Boutique Heritage Inn {city_code}",
                    "city": city_code,
                    "neighborhood": "Old Town",
                    "latitude": 40.7150,
                    "longitude": -74.0080,
                    "star_rating": 4.0,
                    "review_score": 8.6,
                    "price_per_night": 145.00,
                    "currency": "USD",
                    "address": f"45 Heritage Way, {city_code}",
                    "amenities": ["Rooftop Terrace", "Bar", "Concierge"],
                    "amadeus_hotel_id": f"{city_code}BHI02",
                    "photo_url": "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=600",
                }
            ]

        results = []
        for h in hotels:
            item = dict(h)
            item["affiliate_booking_url"] = self.affiliate_service.build_hotel_deep_link(
                hotel_name=item["name"],
                city=item["city"],
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                guests=guests
            )
            results.append(item)

        return results

    def validate_flight_price(self, raw_offer: Dict[str, Any]) -> Dict[str, Any]:
        """Mock price validation always succeeds and confirms availability."""
        return {
            "is_valid": True,
            "price_changed": False,
            "current_total": raw_offer.get("total_amount", 0.0),
            "currency": raw_offer.get("currency", "USD"),
            "status": "CONFIRMED_AVAILABLE"
        }

