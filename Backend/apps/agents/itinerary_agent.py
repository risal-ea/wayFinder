import datetime
from typing import Dict, Any, List
from .tools.travel_tools import tool_save_itinerary_day

class ItinerarySpecialistAgent:
    """
    Itinerary Specialist Agent:
    - Generates morning, afternoon, and evening activity blocks.
    - Clustered by geographic proximity and neighborhood.
    - Writes directly into the Django ItineraryDay database table.
    """

    DESTINATION_TEMPLATES = {
        "TOKYO": [
            {
                "theme": "Historic Asakusa & Modern Akihabara",
                "activities": [
                    {"time_of_day": "morning", "title": "Senso-ji Temple & Nakamise-dori", "description": "Explore Tokyo's oldest Buddhist temple and traditional street food snacks.", "location": "Asakusa", "estimated_cost": 15.0},
                    {"time_of_day": "afternoon", "title": "Akihabara Electric Town & Mandarake", "description": "Visit iconic retro gaming arcades and electronics markets.", "location": "Akihabara", "estimated_cost": 30.0},
                    {"time_of_day": "evening", "title": "Sumida River Cruise & Izakaya Dinner", "description": "Scenic boat cruise followed by yakitori under the train tracks.", "location": "Yurakucho", "estimated_cost": 45.0},
                ],
                "day_cost": 90.0,
            },
            {
                "theme": "Vibrant Shibuya & Harajuku Fashion",
                "activities": [
                    {"time_of_day": "morning", "title": "Meiji Jingu Shrine & Yoyogi Park", "description": "Peaceful forested shrine in the heart of Tokyo.", "location": "Harajuku", "estimated_cost": 0.0},
                    {"time_of_day": "afternoon", "title": "Takeshita Street & Shibuya Crossing", "description": "Trendy youth culture, crepes, and the world's busiest intersection.", "location": "Shibuya", "estimated_cost": 35.0},
                    {"time_of_day": "evening", "title": "Shibuya Sky Panoramic Deck", "description": "360-degree open-air observation deck overlooking Tokyo skyline.", "location": "Shibuya", "estimated_cost": 22.0},
                ],
                "day_cost": 57.0,
            },
            {
                "theme": "Cultural Ueno & Ginza Luxury",
                "activities": [
                    {"time_of_day": "morning", "title": "Tokyo National Museum & Ueno Park", "description": "Masterpieces of Japanese art, samurai armor, and ancient ceramics.", "location": "Ueno", "estimated_cost": 20.0},
                    {"time_of_day": "afternoon", "title": "Ameyoko Market Shopping", "description": "Bustling open-air street market with street food and spice stalls.", "location": "Ueno", "estimated_cost": 25.0},
                    {"time_of_day": "evening", "title": "Ginza Six Rooftop Garden & Ramen Dining", "description": "Architecture walk and Michelin-guide ramen dinner.", "location": "Ginza", "estimated_cost": 40.0},
                ],
                "day_cost": 85.0,
            },
            {
                "theme": "Futuristic Odaiba & TeamLab Borderless",
                "activities": [
                    {"time_of_day": "morning", "title": "TeamLab Borderless Digital Art Museum", "description": "World-famous immersive digital art exhibition.", "location": "Odaiba / Azabudai Hills", "estimated_cost": 38.0},
                    {"time_of_day": "afternoon", "title": "Odaiba Seaside Park & Gundam Statue", "description": "Waterfront boardwalk with views of the Rainbow Bridge.", "location": "Odaiba", "estimated_cost": 15.0},
                    {"time_of_day": "evening", "title": "Monorail Yurikamome Night Ride & Dining", "description": "Elevated train ride across the illuminated Tokyo Bay.", "location": "Tokyo Bay", "estimated_cost": 50.0},
                ],
                "day_cost": 103.0,
            },
            {
                "theme": "Shinjuku Gyoen & Omoide Yokocho",
                "activities": [
                    {"time_of_day": "morning", "title": "Shinjuku Gyoen National Garden", "description": "Tranquil blend of traditional Japanese, English, and French gardens.", "location": "Shinjuku", "estimated_cost": 5.0},
                    {"time_of_day": "afternoon", "title": "Tokyo Metropolitan Government Building View", "description": "Free observation deck on the 45th floor.", "location": "Nishi-Shinjuku", "estimated_cost": 0.0},
                    {"time_of_day": "evening", "title": "Omoide Yokocho (Memory Lane) Dining", "description": "Atmospheric alleyways filled with lanterns and artisanal kushiyaki.", "location": "Shinjuku", "estimated_cost": 40.0},
                ],
                "day_cost": 45.0,
            },
        ],
        "PARIS": [
            {
                "theme": "Iconic Monuments & Seine River",
                "activities": [
                    {"time_of_day": "morning", "title": "Eiffel Tower & Champ de Mars", "description": "Ascend the iconic Iron Lady for panoramic views across Paris.", "location": "7th Arr.", "estimated_cost": 35.0},
                    {"time_of_day": "afternoon", "title": "Musée d'Orsay Impressionist Masters", "description": "Van Gogh, Monet, and Renoir inside a stunning Beaux-Arts station.", "location": "7th Arr.", "estimated_cost": 20.0},
                    {"time_of_day": "evening", "title": "Sunset Seine River Cruise & Bistro Dinner", "description": "Glide past illuminated bridges and dine at a classic Latin Quarter bistro.", "location": "Latin Quarter", "estimated_cost": 65.0},
                ],
                "day_cost": 120.0,
            },
            {
                "theme": "Historic Marais & Louvre Treasures",
                "activities": [
                    {"time_of_day": "morning", "title": "The Louvre Museum Highlights", "description": "Mona Lisa, Winged Victory, and the Venus de Milo.", "location": "1st Arr.", "estimated_cost": 22.0},
                    {"time_of_day": "afternoon", "title": "Le Marais Boutiques & Place des Vosges", "description": "Stroll cobblestone alleys, courtyards, and artisanal bakeries.", "location": "4th Arr.", "estimated_cost": 25.0},
                    {"time_of_day": "evening", "title": "Wine & Cheese Tasting in Saint-Germain", "description": "Curated French wine tasting pairing regional cheeses.", "location": "Saint-Germain", "estimated_cost": 55.0},
                ],
                "day_cost": 102.0,
            },
        ]
    }

    def generate_and_save_itinerary(
        self,
        trip_id: str,
        destination: str,
        start_date_str: str,
        end_date_str: str
    ) -> List[Dict[str, Any]]:
        start_date = datetime.date.fromisoformat(start_date_str)
        end_date = datetime.date.fromisoformat(end_date_str)
        num_days = max((end_date - start_date).days + 1, 1)

        dest_key = destination.upper()
        if "TOKYO" in dest_key or dest_key in ("NRT", "HND", "TYO"):
            templates = self.DESTINATION_TEMPLATES["TOKYO"]
        elif "PARIS" in dest_key or dest_key in ("CDG", "ORY", "PAR"):
            templates = self.DESTINATION_TEMPLATES["PARIS"]
        else:
            # Generic fallback template
            templates = [
                {
                    "theme": f"Discovering Downtown {destination}",
                    "activities": [
                        {"time_of_day": "morning", "title": "City Center Walking Tour", "description": "Explore historic landmarks and architecture.", "location": "Downtown", "estimated_cost": 15.0},
                        {"time_of_day": "afternoon", "title": "Local Market & Cultural Center", "description": "Sample regional delicacies and artisan crafts.", "location": "Market District", "estimated_cost": 25.0},
                        {"time_of_day": "evening", "title": "Rooftop Dining & Skyline Views", "description": "Enjoy traditional local cuisine with skyline views.", "location": "Harbor / Center", "estimated_cost": 45.0},
                    ],
                    "day_cost": 85.0,
                }
            ]

        saved_days = []
        for day_idx in range(num_days):
            day_number = day_idx + 1
            cur_date = start_date + datetime.timedelta(days=day_idx)
            template = templates[day_idx % len(templates)]

            result = tool_save_itinerary_day(
                trip_id=trip_id,
                day_number=day_number,
                date=cur_date.isoformat(),
                theme=f"{template['theme']} (Day {day_number})",
                activities=template["activities"],
                day_cost=template["day_cost"]
            )
            saved_days.append(result)

        return saved_days

