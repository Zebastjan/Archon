"""
Crawl Provider Factory

Creates and configures crawl providers based on user preferences and configuration.
Handles fallback logic when preferred provider is unavailable or fails.
"""


from ...config.logfire_config import get_logger, safe_logfire_info, safe_logfire_warning
from ...utils import get_supabase_client
from ..credential_service import credential_service
from .providers.base_provider import BaseWebCrawlProvider
from .providers.crawl4ai_provider import Crawl4aiProvider
from .providers.tavily_provider import TavilyProvider

logger = get_logger(__name__)


class CrawlProviderFactory:
    """
    Factory for creating crawl provider instances.

    Handles provider selection, configuration, and fallback logic.
    """

    @staticmethod
    async def get_provider(
        provider_name: str | None = None,
        fallback_on_error: bool = True,
        crawler=None,
        supabase_client=None,
    ) -> BaseWebCrawlProvider:
        """
        Get a configured crawl provider instance.

        Args:
            provider_name: Provider to use ("tavily", "crawl4ai", or None for default)
            fallback_on_error: Whether to fallback to Crawl4AI if Tavily fails
            crawler: Crawl4AI crawler instance (required for Crawl4AI provider)
            supabase_client: Supabase client for database operations

        Returns:
            Configured BaseWebCrawlProvider instance

        Raises:
            ValueError: If no provider can be initialized
        """
        supabase_client = supabase_client or get_supabase_client()

        # Get default provider from settings if not specified
        if not provider_name:
            try:
                provider_name = await credential_service.get_credential("DEFAULT_CRAWL_PROVIDER", default="tavily")
            except Exception as e:
                logger.warning(f"Failed to get DEFAULT_CRAWL_PROVIDER setting: {e}, defaulting to tavily")
                provider_name = "tavily"

        safe_logfire_info(f"Provider factory: requested provider={provider_name}, fallback={fallback_on_error}")

        # Try requested provider
        if provider_name == "tavily":
            try:
                return await CrawlProviderFactory._get_tavily_provider(fallback_on_error, crawler, supabase_client)
            except Exception as e:
                if fallback_on_error:
                    safe_logfire_warning(f"Failed to initialize Tavily provider: {e}, falling back to Crawl4AI")
                    return await CrawlProviderFactory._get_crawl4ai_provider(crawler, supabase_client)
                else:
                    raise

        # Default to Crawl4AI or explicit request
        return await CrawlProviderFactory._get_crawl4ai_provider(crawler, supabase_client)

    @staticmethod
    async def _get_tavily_provider(
        fallback_on_error: bool, crawler=None, supabase_client=None
    ) -> BaseWebCrawlProvider:
        """
        Create Tavily provider instance.

        Args:
            fallback_on_error: Whether to fallback to Crawl4AI on error
            crawler: Crawl4AI crawler instance (for fallback)
            supabase_client: Supabase client (for fallback)

        Returns:
            TavilyProvider instance

        Raises:
            ValueError: If Tavily API key not configured and fallback disabled
        """
        # Get Tavily API key from credential service
        try:
            tavily_key = await credential_service.get_credential("TAVILY_API_KEY")
        except Exception as e:
            logger.warning(f"Failed to get Tavily API key: {e}")
            tavily_key = None

        # Check if API key is available
        if not tavily_key:
            if fallback_on_error:
                safe_logfire_warning("Tavily API key not configured, falling back to Crawl4AI")
                return await CrawlProviderFactory._get_crawl4ai_provider(crawler, supabase_client)
            else:
                raise ValueError(
                    "Tavily API key not configured. Set TAVILY_API_KEY in Settings or enable fallback."
                )

        # Create Tavily provider
        provider = TavilyProvider(api_key=tavily_key)

        # Validate configuration
        is_valid, error_message = await provider.validate_configuration()
        if not is_valid:
            if fallback_on_error:
                safe_logfire_warning(f"Tavily configuration invalid: {error_message}, falling back to Crawl4AI")
                return await CrawlProviderFactory._get_crawl4ai_provider(crawler, supabase_client)
            else:
                raise ValueError(f"Tavily provider configuration invalid: {error_message}")

        safe_logfire_info("Tavily provider initialized successfully")
        return provider

    @staticmethod
    async def _get_crawl4ai_provider(crawler=None, supabase_client=None) -> BaseWebCrawlProvider:
        """
        Create Crawl4AI provider instance.

        Args:
            crawler: Crawl4AI crawler instance
            supabase_client: Supabase client for database operations

        Returns:
            Crawl4aiProvider instance

        Raises:
            ValueError: If crawler instance not provided
        """
        if not crawler:
            # Try to get default crawler from crawler manager
            try:
                from ..crawler_manager import get_crawler

                crawler = await get_crawler()
            except Exception as e:
                raise ValueError(f"Failed to get Crawl4AI crawler instance: {e}") from e

        supabase_client = supabase_client or get_supabase_client()

        provider = Crawl4aiProvider(crawler=crawler, supabase_client=supabase_client)

        # Validate configuration
        is_valid, error_message = await provider.validate_configuration()
        if not is_valid:
            raise ValueError(f"Crawl4AI provider configuration invalid: {error_message}")

        safe_logfire_info("Crawl4AI provider initialized successfully")
        return provider
