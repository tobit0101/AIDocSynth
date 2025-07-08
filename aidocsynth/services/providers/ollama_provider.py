import asyncio
import logging
from typing import List, Optional, Callable, Any

from ollama import AsyncClient, ResponseError, ChatResponse
from .base import ProviderBase, register

logger = logging.getLogger(__name__)

@register
class OllamaProvider(ProviderBase):
    name = "ollama"

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def get_models(self, **kwargs) -> List[str]:
        """
        Fetches the list of available models from the Ollama host configured in this provider instance.
        
        Returns:
            List of model names available on the server
            
        Raises:
            ValueError: If Ollama host URL is not configured
            ResponseError: If the Ollama API returns an error
        """
        self.logger.debug(f"OllamaProvider get_models called. self type: {type(self)}")
        
        if not self.host:
            raise ValueError("Ollama host URL is not configured for this provider instance.")
            
        if not self.cli:
            raise ValueError("Ollama client is not initialized")
        
        # Use the list_models method which already has proper error handling
        return await self.list_models()

    async def close(self):
        """Closes the Ollama async client, with resilience for missing aclose method."""
        if not hasattr(self, 'cli') or not self.cli:
            self.logger.info("No active Ollama client (self.cli) to close.")
            return
            
        client_instance = self.cli
        client_type = type(client_instance)
        self.logger.debug(f"Attempting to close Ollama client (type: {client_type})...")
        
        # Try multiple closing methods in order of preference
        closed = False
        
        # Method 1: Try aclose() - standard async close method
        if hasattr(client_instance, 'aclose') and callable(client_instance.aclose):
            try:
                await client_instance.aclose()
                self.logger.debug("Ollama client closed successfully via aclose().")
                closed = True
            except Exception as e:
                self.logger.warning(f"Error during Ollama client aclose(): {e}")
        
        # Method 2: Try __aexit__ - async context manager exit
        if not closed and hasattr(client_instance, '__aexit__') and callable(client_instance.__aexit__):
            try:
                await client_instance.__aexit__(None, None, None)
                self.logger.debug("Ollama client context exited successfully via __aexit__.")
                closed = True
            except Exception as e:
                self.logger.warning(f"Error during Ollama client __aexit__: {e}")
        
        # Method 3: Try close() - some clients might have a synchronous close
        if not closed and hasattr(client_instance, 'close') and callable(client_instance.close):
            try:
                client_instance.close()
                self.logger.debug("Ollama client closed successfully via synchronous close().")
                closed = True
            except Exception as e:
                self.logger.warning(f"Error during Ollama client close(): {e}")
        
        # If none of the methods worked, log a warning but don't raise an exception
        if not closed:
            self.logger.warning(
                f"Ollama client (type: {client_type}) does not have a usable close method. "
                "This is expected with some versions of the ollama library and won't affect functionality."
            )
        
        # Clear the client reference to prevent reuse after close attempt
        self.cli = None

    def __init__(self, cfg):
        logger.debug(f"OllamaProvider __init__ called. self type: {type(self)}, cfg type: {type(cfg)}")
        super().__init__(cfg)
        self.model = cfg.ollama_model
        self.host = cfg.ollama_host
        
        # Initialize client with error handling
        try:
            self.cli = AsyncClient(host=self.host)
            logger.debug(f"Initialized Ollama AsyncClient with host: {self.host}")
        except Exception as e:
            logger.error(f"Failed to initialize Ollama AsyncClient: {e}", exc_info=True)
            self.cli = None
            # We don't raise here to allow the application to continue,
            # but operations will fail later if they try to use self.cli

    async def _wait_with_cancellation(self, awaitable_task, is_cancelled_callback: Optional[Callable[[], bool]] = None, poll_interval: float = 0.5) -> Any:
        """
        Waits for awaitable_task to complete, but polls for cancellation.
        
        Args:
            awaitable_task: The async task to wait for
            is_cancelled_callback: Function that returns True if operation should be cancelled
            poll_interval: How frequently to check for cancellation, in seconds
            
        Returns:
            The result of awaitable_task if it completes successfully
            
        Raises:
            asyncio.CancelledError: If the operation was cancelled via is_cancelled_callback
        """
        # If no cancellation callback provided, just await the task directly
        if not is_cancelled_callback:
            return await awaitable_task

        # Create a task for the API call
        api_call_task = asyncio.create_task(awaitable_task)
        
        try:
            # Poll until the task completes or cancellation is requested
            while not api_call_task.done():
                # Check if cancellation was requested
                if is_cancelled_callback():
                    self.logger.info("Cancellation requested, aborting Ollama API call")
                    api_call_task.cancel()
                    # Give the task a moment to acknowledge cancellation
                    try:
                        await asyncio.wait_for(api_call_task, timeout=0.1)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
                    raise asyncio.CancelledError("LLM call cancelled by user request.")
                
                # Wait a bit before checking again, but don't block cancellation
                try:
                    # Shield prevents the wait_for timeout from cancelling the actual API task
                    await asyncio.wait_for(asyncio.shield(api_call_task), timeout=poll_interval)
                except asyncio.TimeoutError:
                    # This is expected - we're just polling
                    pass
                    
            # Task completed normally, return the result
            return await api_call_task
            
        except Exception as e:
            # If any other exception occurs, ensure the task is cancelled
            if not api_call_task.done():
                api_call_task.cancel()
            # Re-raise the original exception
            raise

    async def _run(self, messages: list, is_cancelled_callback: Optional[Callable[[], bool]] = None):
        """
        Execute the LLM call with the given messages, supporting cancellation.
        
        Args:
            messages: List of message objects to send to the model
            is_cancelled_callback: Function that returns True if operation should be cancelled
            
        Returns:
            The content of the model's response
            
        Raises:
            asyncio.CancelledError: If the operation was cancelled
            ResponseError: If the Ollama API returns an error
            ValueError: If the client is not initialized or response format is invalid
        """
        if not self.cli:
            raise ValueError("Ollama client is not initialized")
            
        # Log the request (excluding potentially large message content)
        self.logger.debug(f"Sending request to Ollama model: {self.model}")
        
        try:
            # Prepare the API call
            chat_call = self.cli.chat(
                model=self.model,
                messages=messages,
                stream=False,
                format="json",
                options={"temperature": 0.1}
            )
            
            # Wait for response with cancellation support
            response_data = await self._wait_with_cancellation(chat_call, is_cancelled_callback)
            
            # The response_data is a ChatResponse object. We access its fields via attributes.
            if not isinstance(response_data, ChatResponse) or not hasattr(response_data, 'message'):
                raise ValueError(f"Unexpected response format from Ollama: {type(response_data)}")

            message = response_data.message
            if not hasattr(message, 'content'):
                raise ValueError("Ollama response is missing 'content' in the message")

            content = message.content
            if not isinstance(content, str):
                raise ValueError(f"Ollama response content is not a string: {type(content)}")

            return content
            
        except ResponseError as e:
            self.logger.error(f"Ollama API error: {e}")
            raise
        except asyncio.CancelledError:
            self.logger.info("Ollama request cancelled")
            raise
        except Exception as e:
            self.logger.error(f"Error during Ollama request: {e}", exc_info=True)
            raise

    async def list_models(self) -> List[str]:
        """
        List available models from the Ollama server.
        
        Returns:
            List of model names available on the server
        """
        if not self.cli:
            self.logger.error("Cannot list models: Ollama client is not initialized")
            return []
            
        try:
            # Use _wait_with_cancellation to support cancellation during model listing
            list_call = self.cli.list()
            response_data = await self._wait_with_cancellation(list_call, None)
            
            model_entries = response_data.get('models', [])  # list of ollama.ModelResponse
            
            extracted_names = []
            for entry in model_entries:
                model_name = entry.get('name') or entry.get('model')
                if model_name:
                    # Ensure we have a string to prevent Qt segfaults with C-level pointers
                    extracted_names.append(str(model_name))
                else:
                    self.logger.warning(f"Ollama model entry missing both 'name' and 'model' fields. Entry: {entry}")
            
            if not extracted_names and model_entries:
                self.logger.info("No model names extracted from Ollama despite model entries being present. Raw entries: %s", model_entries)
            
            return sorted(extracted_names)
            
        except ResponseError as e:
            # Log the host/base_url for easier debugging of connection issues
            host_url = getattr(self.cli, '_host', 'N/A')
            self.logger.error(f"Ollama API error while listing models from {host_url}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error while listing Ollama models: {e}", exc_info=True)
            return []
