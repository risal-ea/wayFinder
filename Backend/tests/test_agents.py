import pytest
from apps.agents.tools.travel_tools import (
    tool_search_flights,
    tool_search_hotels,
    tool_create_or_get_trip,
    tool_save_itinerary_day,
    tool_calculate_trip_budget,
    execute_tool,
)
from apps.agents.coordinator import TravelCoordinatorAgent

@pytest.mark.django_db
def test_mcp_tools():
    # Test flight search tool
    res_flights = tool_search_flights(origin="JFK", destination="NRT", departure_date="2026-05-10")
    assert res_flights["count"] > 0
    flight_id = res_flights["offers"][0]["id"]

    # Test hotel search tool
    res_hotels = tool_search_hotels(city_code="TYO", check_in_date="2026-05-10", check_out_date="2026-05-15")
    assert res_hotels["count"] > 0
    assert "booking.com" in res_hotels["hotels"][0]["affiliate_booking_url"]

    # Test trip creation tool
    res_trip = tool_create_or_get_trip(
        title="Agent Tokyo Trip",
        origin="JFK",
        destination="Tokyo",
        start_date="2026-05-10",
        end_date="2026-05-15",
        budget_ceiling=2500.0,
    )
    trip_id = res_trip["trip_id"]

    # Test itinerary day tool
    res_day = tool_save_itinerary_day(
        trip_id=trip_id,
        day_number=1,
        date="2026-05-10",
        theme="Historic Asakusa",
        activities=[{"time_of_day": "morning", "title": "Senso-ji Temple", "location": "Asakusa"}],
        day_cost=50.0
    )
    assert res_day["day_number"] == 1

    # Test budget tool
    budget = tool_calculate_trip_budget(trip_id=trip_id)
    assert budget["budget_ceiling"] == 2500.0
    assert budget["within_budget"] is True

@pytest.mark.django_db
def test_coordinator_agent_plan_trip():
    coordinator = TravelCoordinatorAgent()
    proposal = coordinator.plan_trip("Plan a 5-day trip to Tokyo from JFK under $3000")

    assert "narrative" in proposal
    assert "trip" in proposal
    assert proposal["trip"]["destination_city"] == "Tokyo"
    assert len(proposal["trip"]["days"]) == 5
    assert len(proposal["trip"]["shortlist_items"]) >= 2
    assert proposal["flight_recommendation"]["airline"] is not None
    assert "booking.com" in proposal["hotel_recommendation"]["affiliate_booking_url"]

