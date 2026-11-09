from django.urls import path
from .views import AgentPlanAPIView, AgentChatAPIView, AgentFlightSearchAPIView, MCPToolsListAPIView

urlpatterns = [
    path('plan/', AgentPlanAPIView.as_view(), name='agent-plan'),
    path('chat/', AgentChatAPIView.as_view(), name='agent-chat'),
    path('flights/search/', AgentFlightSearchAPIView.as_view(), name='agent-flights-search'),
    path('tools/', MCPToolsListAPIView.as_view(), name='mcp-tools'),
]
