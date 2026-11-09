import datetime
from decimal import Decimal
from typing import List, Dict, Any
from django.utils import timezone
from apps.catalog.models import Airport, MasterHotel, FlightOffer
from apps.providers.factory import get_travel_provider

class TravelIngestionService:
    """
    Normalizes provider feeds and ingests them into the Django Centralized Database.
    """

    def __init__(self, provider=None):
        self.provider = provider or get_travel_provider()

    def get_or_create_airport(self, iata_code: str, city_name: str = "") -> Airport:
        """Finds or creates an Airport stub to ensure relational foreign-key integrity."""
        code = iata_code.upper()
        airport, created = Airport.objects.get_or_create(
            iata_code=code,
            defaults={
                "name": f"{code} International Airport",
                "city_name": city_name or code,
                "country_code": "XX",
                "latitude": Decimal("0.0"),
                "longitude": Decimal("0.0"),
            }
        )
        return airport

    def ingest_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str = None,
        passengers: int = 1,
        cabin_class: str = "economy"
    ) -> List[FlightOffer]:
        """
        Fetches flights from provider, saves normalized FlightOffers with 20 min TTL, and returns them.
        """
        raw_offers = self.provider.search_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            passengers=passengers,
            cabin_class=cabin_class
        )

        origin_airport = self.get_or_create_airport(origin)
        destination_airport = self.get_or_create_airport(destination)
        now = timezone.now()
        ttl_minutes = 20
        expires_at = now + datetime.timedelta(minutes=ttl_minutes)

        saved_offers = []
        for raw in raw_offers:
            dep_time_raw = raw["departure_time"]
            arr_time_raw = raw["arrival_time"]
            
            dep_dt = datetime.datetime.fromisoformat(dep_time_raw)
            arr_dt = datetime.datetime.fromisoformat(arr_time_raw)
            if timezone.is_naive(dep_dt):
                dep_dt = timezone.make_aware(dep_dt)
            if timezone.is_naive(arr_dt):
                arr_dt = timezone.make_aware(arr_dt)

            ret_dep_dt = None
            ret_arr_dt = None
            if raw.get("return_departure_time"):
                ret_dep_dt = datetime.datetime.fromisoformat(raw["return_departure_time"])
                if timezone.is_naive(ret_dep_dt):
                    ret_dep_dt = timezone.make_aware(ret_dep_dt)
            if raw.get("return_arrival_time"):
                ret_arr_dt = datetime.datetime.fromisoformat(raw["return_arrival_time"])
                if timezone.is_naive(ret_arr_dt):
                    ret_arr_dt = timezone.make_aware(ret_arr_dt)

            total_amt = Decimal(str(raw["total_amount"]))
            base_amt = Decimal(str(raw.get("base_amount", round(float(total_amt) * 0.85, 2))))
            tax_amt = Decimal(str(raw.get("tax_amount", round(float(total_amt) - float(base_amt), 2))))

            offer = FlightOffer.objects.create(
                provider=raw.get("provider", "amadeus"),
                provider_offer_id=raw["provider_offer_id"],
                airline_name=raw["airline_name"],
                flight_number=raw["flight_number"],
                origin_airport=origin_airport,
                destination_airport=destination_airport,
                departure_time=dep_dt,
                arrival_time=arr_dt,
                duration_minutes=raw["duration_minutes"],
                stops=raw["stops"],
                cabin_class=raw["cabin_class"],
                is_round_trip=raw.get("is_round_trip", bool(return_date)),
                return_departure_time=ret_dep_dt,
                return_arrival_time=ret_arr_dt,
                return_flight_number=raw.get("return_flight_number", ""),
                segments_json=raw.get("segments", []),
                raw_amadeus_offer=raw.get("raw_amadeus_offer", {}),
                base_amount=base_amt,
                tax_amount=tax_amt,
                total_amount=total_amt,
                currency=raw.get("currency", "USD"),
                cabin_bags=raw.get("cabin_bags", 1),
                checked_bags=raw.get("checked_bags", 1),
                is_refundable=raw.get("is_refundable", False),
                expires_at=expires_at,
                booking_url=raw.get("booking_url", ""),
            )
            saved_offers.append(offer)

        return saved_offers

    def ingest_hotels(
        self,
        city_code: str,
        check_in_date: str,
        check_out_date: str,
        guests: int = 1
    ) -> List[MasterHotel]:
        """
        Fetches hotels from provider, de-duplicates and updates/creates MasterHotel records.
        """
        raw_hotels = self.provider.search_hotels(
            city_code=city_code,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            guests=guests
        )

        saved_hotels = []
        for raw in raw_hotels:
            amadeus_id = raw.get("amadeus_hotel_id", "")
            name = raw["name"]
            city = raw.get("city", city_code)

            # De-duplicate by amadeus_id if present, else by name and city
            lookup = {"amadeus_hotel_id": amadeus_id} if amadeus_id else {"name": name, "city": city}
            
            lat = Decimal(str(raw["latitude"])) if raw.get("latitude") is not None else None
            lon = Decimal(str(raw["longitude"])) if raw.get("longitude") is not None else None

            hotel, _ = MasterHotel.objects.update_or_create(
                **lookup,
                defaults={
                    "name": name,
                    "city": city,
                    "neighborhood": raw.get("neighborhood", ""),
                    "latitude": lat,
                    "longitude": lon,
                    "star_rating": Decimal(str(raw.get("star_rating", 4.0))),
                    "review_score": Decimal(str(raw.get("review_score", 8.5))),
                    "price_per_night": Decimal(str(raw.get("price_per_night", 150.00))),
                    "currency": raw.get("currency", "USD"),
                    "amadeus_hotel_id": amadeus_id,
                    "address": raw.get("address", ""),
                    "photo_url": raw.get("photo_url", ""),
                    "amenities": raw.get("amenities", []),
                    "affiliate_booking_url": raw.get("affiliate_booking_url", ""),
                }
            )
            saved_hotels.append(hotel)

        return saved_hotels

