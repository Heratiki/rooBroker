import http.server
import socketserver
import json
import requests
from urllib.parse import urlparse, parse_qs
import threading
import time

# Configuration
LM_STUDIO_HOST = "localhost"
LM_STUDIO_PORT = 1234
PROXY_PORT = 1235  # The proxy will run on this port
LM_STUDIO_MODELS_ENDPOINT = f"http://{LM_STUDIO_HOST}:{LM_STUDIO_PORT}/v1/models"
LM_STUDIO_CHAT_ENDPOINT = f"http://{LM_STUDIO_HOST}:{LM_STUDIO_PORT}/v1/chat/completions"

# Cache for model context windows
model_context_cache = {}
last_cache_update = 0
CACHE_TTL = 300  # 5 minutes

def update_model_context_cache():
    """Update the cache of model context window information"""
    global model_context_cache, last_cache_update
    try:
        response = requests.get(LM_STUDIO_MODELS_ENDPOINT, timeout=5)
        if response.status_code == 200:
            models_data = response.json().get("data", [])
            
            for model in models_data:
                model_id = model.get("id") or model.get("name")
                if model_id:
                    context_length = model.get("context_length") or model.get("context_window")
                    if context_length and isinstance(context_length, (int, float)):
                        model_context_cache[model_id] = int(context_length)
                        print(f"Cached context window for {model_id}: {context_length}")
                    
            last_cache_update = time.time()
            print(f"Updated model context cache with {len(model_context_cache)} models")
    except Exception as e:
        print(f"Error updating model context cache: {e}")

class LMStudioProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests by forwarding them to LM Studio"""
        parsed_path = urlparse(self.path)
        
        # Forward the request to LM Studio
        target_url = f"http://{LM_STUDIO_HOST}:{LM_STUDIO_PORT}{parsed_path.path}"
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
        """Handle POST requests, optimizing context window settings"""
        # Check if cache needs updating
        global last_cache_update
        if time.time() - last_cache_update > CACHE_TTL:
            update_model_context_cache()
        
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
            if model_id and model_id in model_context_cache:
                # Get the model's context window size
                context_window = model_context_cache[model_id]
                
                # Calculate optimal max_tokens (25% of context for response)
                current_max_tokens = request_json.get("max_tokens", 2048)
                optimal_max_tokens = min(current_max_tokens, max(1024, int(context_window * 0.25)))
                
                # Update the request to use the optimal max_tokens
                request_json["max_tokens"] = optimal_max_tokens
                print(f"Optimized request for {model_id}: set max_tokens to {optimal_max_tokens} (context window: {context_window})")
                
                # Convert the modified request back to bytes
                post_data = json.dumps(request_json).encode('utf-8')
        
        # Forward the request to LM Studio
        target_url = f"http://{LM_STUDIO_HOST}:{LM_STUDIO_PORT}{parsed_path.path}"
        
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
    
    def log_message(self, format, *args):
        """Override logging to provide more useful information"""
        print(f"{self.client_address[0]} - {args[0].split()[0]} {args[0].split()[1]}")

def run_proxy_server():
    """Run the LM Studio proxy server"""
    # Initialize the model context cache
    update_model_context_cache()
    
    # Create and run the proxy server
    handler = LMStudioProxyHandler
    with socketserver.TCPServer(("", PROXY_PORT), handler) as httpd:
        print(f"LM Studio Context Optimizer Proxy running on port {PROXY_PORT}")
        print(f"Point Roo Code to use http://localhost:{PROXY_PORT} instead of http://localhost:{LM_STUDIO_PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_proxy_server()