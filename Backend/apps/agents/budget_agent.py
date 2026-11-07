from typing import Dict, Any
from .tools.travel_tools import tool_calculate_trip_budget

class BudgetSpecialistAgent:
    """
    Budget Specialist Agent:
    - Sums flight, hotel, and activity expenses.
    - Validates against user budget ceiling.
    - Suggests cost optimization if budget is exceeded.
    """

    def analyze_trip_budget(self, trip_id: str) -> Dict[str, Any]:
        budget_summary = tool_calculate_trip_budget(trip_id=trip_id)
        within_budget = budget_summary["within_budget"]
        remaining = budget_summary["remaining_budget"]

        if within_budget:
            message = f"Trip is fully within budget! Remaining cushion: ${remaining:,.2f} {budget_summary['currency']}."
        else:
            message = f"Alert: Trip exceeds budget ceiling by ${abs(remaining):,.2f} {budget_summary['currency']}. Consider selecting a 4-star accommodation or alternate flight cabin."

        return {
            **budget_summary,
            "status": "APPROVED" if within_budget else "WARNING_OVER_BUDGET",
            "advisory_message": message,
        }

