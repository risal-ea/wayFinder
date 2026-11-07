import logging
from django.conf import settings
from apps.providers.base import BaseTravelProvider
from apps.providers.mock_client import MockTravelProvider
from apps.providers.amadeus_client import AmadeusProviderService

logger = logging.getLogger(__name__)

def get_travel_provider() -> BaseTravelProvider:
    """
    Factory function returning the active provider.
    Defaults to MockTravelProvider if PROVIDER_MODE == 'mock' or if Amadeus keys are missing.
    """
    mode = getattr(settings, "PROVIDER_MODE", "mock").lower()
    client_id = getattr(settings, "AMADEUS_CLIENT_ID", "")
    client_secret = getattr(settings, "AMADEUS_CLIENT_SECRET", "")

    if mode == "amadeus":
        if client_id and client_secret:
            logger.info("Using AmadeusProviderService (Live API)")
            return AmadeusProviderService()
        else:
            logger.warning("PROVIDER_MODE is 'amadeus' but credentials missing. Falling back to MockTravelProvider.")
            return MockTravelProvider()
    
    logger.info("Using MockTravelProvider")
    return MockTravelProvider()

