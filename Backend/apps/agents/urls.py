from django.urls import path
from .views import AgentPlanAPIView, AgentChatAPIView, MCPToolsListAPIView

urlpatterns = [
    path('plan/', AgentPlanAPIView.as_view(), name='agent-plan'),
    path('chat/', AgentChatAPIView.as_view(), name='agent-chat'),
    path('tools/', MCPToolsListAPIView.as_view(), name='mcp-tools'),
]

