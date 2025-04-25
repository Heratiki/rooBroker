"""Core proxy server functionality.

This module provides a context window optimization proxy for model providers.
It intercepts API requests and optimizes parameters based on model capabilities.
"""

import http.server
import socketserver
import json
import requests
import time
from urllib.parse import urlparse  
from typing import Any, Dict, Optional, Tuple, Callable
from rich.console import Console

# Default configuration
DEFAULT_PROXY_PORT = 1235
CACHE_TTL = 300  # 5 minutes


class ModelContextCache:
    """Cache for storing model context window information."""
    
    def __init__(self):
        """Initialize the model context cache."""
        self.model_data: Dict[str, int] = {}
        self.last_update: float = 0.0
    
    def update(self, models_data: Dict[str, Any], console: Optional[Console] = None) -> None:
        """Update the cache with model information.
        
        Args:
            models_data: Dictionary of model information from the API.
            console: Optional Rich console for formatted output.
        """
        if console is None:
            console = Console()
        
        for model in models_data.get("data", []):
            model_id = model.get("id") or model.get("name")
            if model_id:
                context_length = model.get("context_length") or model.get("context_window")
                if context_length and isinstance(context_length, (int, float)):
                    self.model_data[model_id] = int(context_length)
                    console.print(f"Cached context window for {model_id}: {context_length}")
        
        self.last_update = time.time()
        console.print(f"Updated model context cache with {len(self.model_data)} models")
    
    def needs_update(self) -> bool:
        """Check if the cache needs to be updated.
        
        Returns:
            True if the cache TTL has expired, False otherwise.
        """
        return time.time() - self.last_update > CACHE_TTL
    
    def get_context_window(self, model_id: str) -> Optional[int]:
        """Get the context window size for a model.
        
        Args:
            model_id: The ID of the model to get the context window for.
            
        Returns:
            The context window size, or None if not found.
        """
        return self.model_data.get(model_id)


class ContextOptimizerHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for the context optimizer proxy."""
    
    # These will be set when creating the server
    provider_host: str = "localhost"
    provider_port: int = 1234
    cache: ModelContextCache = ModelContextCache()
    console: Console = Console()
    
    # Endpoint templates
    @property
    def provider_base_url(self) -> str:
        """Get the base URL for the provider API."""
        return f"http://{self.provider_host}:{self.provider_port}"
    
    @property
    def provider_models_endpoint(self) -> str:
        """Get the models endpoint URL."""
        return f"{self.provider_base_url}/v1/models"
    
    @property
    def provider_chat_endpoint(self) -> str:
        """Get the chat completions endpoint URL."""
        return f"{self.provider_base_url}/v1/chat/completions"
    
    def update_model_cache(self) -> None:
        """Update the model context window cache."""
        try:
            response = requests.get(self.provider_models_endpoint, timeout=5)
            if response.status_code == 200:
                self.cache.update(response.json(), self.console)
        except Exception as e:
            self.console.print(f"[red]Error updating model context cache: {e}[/red]")
    
    def do_GET(self):
        """Handle GET requests by forwarding them to the provider API."""
        parsed_path = urlparse(self.path)
        
        # Forward the request to the provider
        target_url = f"{self.provider_base_url}{parsed_path.path}"
        if parsed_path.query:
            target_url += f"?{parsed_path.query}"
            
        try:
            # Forward all headers
            headers = {k: v for k, v in self.headers.items()}
            
            response = requests.get(target_url, headers=headers)
            
            # Send the response status code
            self.send_response(response.status_code)
            
            # Send headers
            for header, value in response.headers.items():
                self.send_header(header, value)
            self.end_headers()
            
            # Send the response content
            self.wfile.write(response.content)
            
        except Exception as e:
            self.send_error(500, f"Error forwarding request: {str(e)}")
    
    def do_POST(self):
        """Handle POST requests, optimizing context window settings."""
        # Check if cache needs updating
        if self.cache.needs_update():
            self.update_model_cache()
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            request_json = json.loads(post_data.decode('utf-8'))
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON in request")
            return
        
        # Check if this is a chat completion request that we should optimize
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/v1/chat/completions":
            # Get the model ID from the request
            model_id = request_json.get("model")
            context_window = self.cache.get_context_window(model_id) if model_id else None
            
            if context_window:
                # Calculate optimal max_tokens (25% of context for response)
                current_max_tokens = request_json.get("max_tokens", 2048)
                optimal_max_tokens = min(current_max_tokens, max(1024, int(context_window * 0.25)))
                
                # Update the request to use the optimal max_tokens
                request_json["max_tokens"] = optimal_max_tokens
                self.console.print(
                    f"Optimized request for {model_id}: set max_tokens to {optimal_max_tokens} "
                    f"(context window: {context_window})"
                )
                
                # Convert the modified request back to bytes
                post_data = json.dumps(request_json).encode('utf-8')
        
        # Forward the request to the provider
        target_url = f"{self.provider_base_url}{parsed_path.path}"
        
        try:
            # Forward all headers
            headers = {k: v for k, v in self.headers.items()}
            headers['Content-Length'] = str(len(post_data))
            
            response = requests.post(target_url, data=post_data, headers=headers)
            
            # Send the response status code
            self.send_response(response.status_code)
            
            # Send headers
            for header, value in response.headers.items():
                self.send_header(header, value)
            self.end_headers()
            
            # Send the response content
            self.wfile.write(response.content)
            
        except Exception as e:
            self.send_error(500, f"Error forwarding request: {str(e)}")
    
    def log_message(self, format: str, *args: Any) -> None:
        """Override logging to provide more useful information."""
        self.console.print(f"{self.client_address[0]} - {args[0].split()[0]} {args[0].split()[1]}")


def create_proxy_handler(
    provider_host: str,
    provider_port: int,
    cache: ModelContextCache,
    console: Console
) -> type:
    """Create a customized proxy handler with the given configuration.
    
    Args:
        provider_host: The host of the model provider API.
        provider_port: The port of the model provider API.
        cache: The model context cache to use.
        console: The console for logging.
        
    Returns:
        A customized HTTP request handler class.
    """
    # Create a subclass with the given configuration
    class CustomHandler(ContextOptimizerHandler):
        pass
    
    # Set the configuration on the class
    CustomHandler.provider_host = provider_host
    CustomHandler.provider_port = provider_port
    CustomHandler.cache = cache
    CustomHandler.console = console
    
    return CustomHandler


def run_proxy_server(
    provider_host: str = "localhost",
    provider_port: int = 1234,
    proxy_port: int = DEFAULT_PROXY_PORT,
    console: Optional[Console] = None
) -> socketserver.TCPServer:
    """Run the model provider proxy server.
    
    Args:
        provider_host: The host of the model provider API.
        provider_port: The port of the model provider API.
        proxy_port: The port to run the proxy server on.
        console: Optional Rich console for formatted output.
        
    Returns:
        The TCP server object.
        
    Raises:
        OSError: If the proxy port is already in use.
    """
    if console is None:
        console = Console()
    
    # Create the cache and initialize it
    cache = ModelContextCache()
    
    # Create the handler with the given configuration
    handler = create_proxy_handler(provider_host, provider_port, cache, console)
    
    # Create and run the proxy server
    try:
        server = socketserver.TCPServer(("", proxy_port), handler)
        
        # Initialize the model context cache
        try:
            models_url = f"http://{provider_host}:{provider_port}/v1/models"
            response = requests.get(models_url, timeout=5)
            if response.status_code == 200:
                cache.update(response.json(), console)
        except Exception as e:
            console.print(f"[yellow]Warning: Unable to initialize model cache: {e}[/yellow]")
            console.print("[yellow]The proxy will still work, but without optimization until it can connect to the model provider.[/yellow]")
        
        console.print(f"[green]Context Optimizer Proxy running on port {proxy_port}[/green]")
        console.print(f"[green]Forwarding requests to {provider_host}:{provider_port}[/green]")
        console.print(f"[green]Point API clients to use http://localhost:{proxy_port}[/green]")
        
        return server
    except OSError as e:
        console.print(f"[red]Error starting proxy server: {e}[/red]")
        raise


def run_proxy_in_thread(
    provider_host: str = "localhost",
    provider_port: int = 1234,
    proxy_port: int = DEFAULT_PROXY_PORT,
    console: Optional[Console] = None
) -> Tuple[socketserver.TCPServer, Callable[[], None]]:
    """Run the proxy server in a background thread.
    
    This function creates and starts the proxy server in a separate thread,
    allowing the main program to continue running.
    
    Args:
        provider_host: The host of the model provider API.
        provider_port: The port of the model provider API.
        proxy_port: The port to run the proxy server on.
        console: Optional Rich console for formatted output.
        
    Returns:
        A tuple containing:
        - The TCP server object
        - A function that can be called to stop the server
        
    Raises:
        OSError: If the proxy port is already in use.
    """
    import threading
    
    if console is None:
        console = Console()
    
    server = run_proxy_server(provider_host, provider_port, proxy_port, console)
    
    # Create a thread to run the server
    server_thread = threading.Thread(
        target=server.serve_forever,
        daemon=True  # Allow the program to exit even if the server is still running
    )
    server_thread.start()
    
    # Return a function to stop the server
    def stop_server():
        console.print("[yellow]Stopping proxy server...[/yellow]")
        server.shutdown()
        server.server_close()
        console.print("[green]Proxy server stopped[/green]")
    
    return server, stop_server
