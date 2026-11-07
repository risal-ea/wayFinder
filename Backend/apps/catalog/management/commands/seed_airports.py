from django.core.management.base import BaseCommand
from apps.catalog.models import Airport

GLOBAL_AIRPORTS = [
    {"iata_code": "JFK", "name": "John F. Kennedy International Airport", "city_name": "New York", "country_code": "US", "latitude": 40.6413, "longitude": -73.7781},
    {"iata_code": "EWR", "name": "Newark Liberty International Airport", "city_name": "New York", "country_code": "US", "latitude": 40.6895, "longitude": -74.1745},
    {"iata_code": "LGA", "name": "LaGuardia Airport", "city_name": "New York", "country_code": "US", "latitude": 40.7769, "longitude": -73.8740},
    {"iata_code": "LAX", "name": "Los Angeles International Airport", "city_name": "Los Angeles", "country_code": "US", "latitude": 33.9416, "longitude": -118.4085},
    {"iata_code": "SFO", "name": "San Francisco International Airport", "city_name": "San Francisco", "country_code": "US", "latitude": 37.6213, "longitude": -122.3790},
    {"iata_code": "ORD", "name": "O'Hare International Airport", "city_name": "Chicago", "country_code": "US", "latitude": 41.9742, "longitude": -87.9073},
    {"iata_code": "NRT", "name": "Narita International Airport", "city_name": "Tokyo", "country_code": "JP", "latitude": 35.7720, "longitude": 140.3929},
    {"iata_code": "HND", "name": "Tokyo Haneda Airport", "city_name": "Tokyo", "country_code": "JP", "latitude": 35.5494, "longitude": 139.7798},
    {"iata_code": "KIX", "name": "Kansai International Airport", "city_name": "Osaka", "country_code": "JP", "latitude": 34.4320, "longitude": 135.2304},
    {"iata_code": "LHR", "name": "London Heathrow Airport", "city_name": "London", "country_code": "GB", "latitude": 51.4700, "longitude": -0.4543},
    {"iata_code": "LGW", "name": "London Gatwick Airport", "city_name": "London", "country_code": "GB", "latitude": 51.1537, "longitude": -0.1821},
    {"iata_code": "CDG", "name": "Charles de Gaulle Airport", "city_name": "Paris", "country_code": "FR", "latitude": 49.0097, "longitude": 2.5479},
    {"iata_code": "ORY", "name": "Paris Orly Airport", "city_name": "Paris", "country_code": "FR", "latitude": 48.7262, "longitude": 2.3652},
    {"iata_code": "FRA", "name": "Frankfurt Airport", "city_name": "Frankfurt", "country_code": "DE", "latitude": 50.0379, "longitude": 8.5622},
    {"iata_code": "AMS", "name": "Amsterdam Airport Schiphol", "city_name": "Amsterdam", "country_code": "NL", "latitude": 52.3105, "longitude": 4.7683},
    {"iata_code": "DXB", "name": "Dubai International Airport", "city_name": "Dubai", "country_code": "AE", "latitude": 25.2532, "longitude": 55.3657},
    {"iata_code": "SIN", "name": "Singapore Changi Airport", "city_name": "Singapore", "country_code": "SG", "latitude": 1.3644, "longitude": 103.9915},
    {"iata_code": "BOM", "name": "Chhatrapati Shivaji Maharaj International Airport", "city_name": "Mumbai", "country_code": "IN", "latitude": 19.0896, "longitude": 72.8656},
    {"iata_code": "DEL", "name": "Indira Gandhi International Airport", "city_name": "Delhi", "country_code": "IN", "latitude": 28.5562, "longitude": 77.1000},
    {"iata_code": "BLR", "name": "Kempegowda International Airport", "city_name": "Bengaluru", "country_code": "IN", "latitude": 13.1986, "longitude": 77.7066},
    {"iata_code": "SYD", "name": "Sydney Kingsford Smith Airport", "city_name": "Sydney", "country_code": "AU", "latitude": -33.9399, "longitude": 151.1753},
    {"iata_code": "FCO", "name": "Leonardo da Vinci–Fiumicino Airport", "city_name": "Rome", "country_code": "IT", "latitude": 41.8003, "longitude": 12.2389},
    {"iata_code": "BCN", "name": "Josep Tarradellas Barcelona-El Prat Airport", "city_name": "Barcelona", "country_code": "ES", "latitude": 41.2974, "longitude": 2.0833},
]

class Command(BaseCommand):
    help = "Seeds initial global airports catalog for IATA resolution"

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0
        for airport_data in GLOBAL_AIRPORTS:
            obj, created = Airport.objects.update_or_create(
                iata_code=airport_data["iata_code"],
                defaults={
                    "name": airport_data["name"],
                    "city_name": airport_data["city_name"],
                    "country_code": airport_data["country_code"],
                    "latitude": airport_data["latitude"],
                    "longitude": airport_data["longitude"],
                }
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded airports: {created_count} created, {updated_count} updated."
            )
        )

