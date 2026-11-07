from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .coordinator import TravelCoordinatorAgent
from .tools.travel_tools import TOOL_SCHEMAS, execute_tool

class AgentPlanAPIView(APIView):
    """
    Orchestrates the multi-agent travel team based on a natural language goal.
    Example: "Plan a 5-day trip to Tokyo in May under $2500"
    """
    def post(self, request):
        prompt = request.data.get("prompt")
        if not prompt:
            return Response({"error": "prompt parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        coordinator = TravelCoordinatorAgent()
        proposal = coordinator.plan_trip(prompt)
        return Response(proposal, status=status.HTTP_200_OK)


class AgentChatAPIView(APIView):
    """
    Conversational endpoint interfacing with the Travel Coordinator.
    """
    def post(self, request):
        message = request.data.get("message")
        if not message:
            return Response({"error": "message parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        coordinator = TravelCoordinatorAgent()
        proposal = coordinator.plan_trip(message)
        return Response({
            "response": proposal["narrative"],
            "trip": proposal["trip"],
        }, status=status.HTTP_200_OK)


class MCPToolsListAPIView(APIView):
    """
    Exposes Model Context Protocol (MCP) schemas of all travel tools for LLM agent function calling.
    """
    def get(self, request):
        return Response({
            "mcp_version": "1.0",
            "tools_count": len(TOOL_SCHEMAS),
            "tools": TOOL_SCHEMAS
        }, status=status.HTTP_200_OK)

    def post(self, request):
        tool_name = request.data.get("tool_name")
        arguments = request.data.get("arguments", {})
        if not tool_name:
            return Response({"error": "tool_name is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = execute_tool(tool_name, arguments)
            return Response({"tool": tool_name, "result": result}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

