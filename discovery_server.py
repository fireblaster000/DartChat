"""
Discovery Server Module
Central server for peer discovery and connection coordination
"""
import socket
import threading
import json
import time
from datetime import datetime, timedelta

class DiscoveryServer:
    """
    Central discovery server that maintains a registry of active peers
    and facilitates peer-to-peer connection establishment
    """
    
    def __init__(self, host="0.0.0.0", port=9000):
        self.host = host
        self.port = port
        self.peers = {}  # {username: {"address": (ip, port), "last_seen": timestamp}}
        self.lock = threading.Lock()
        self.running = False
        self.cleanup_interval = 30  # seconds
        self.peer_timeout = 60  # seconds
        
    def start(self):
        """Start the discovery server"""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            print(f"[v0] Discovery server listening on {self.host}:{self.port}")
            
            # Start cleanup thread
            cleanup_thread = threading.Thread(target=self._cleanup_stale_peers, daemon=True)
            cleanup_thread.start()
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    thread.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"[v0] Error accepting connection: {e}")
                        
        except Exception as e:
            print(f"[v0] Failed to start discovery server: {e}")
        finally:
            self.server_socket.close()
    
    def _handle_client(self, client_socket, address):
        """Handle client requests"""
        try:
            data = client_socket.recv(4096).decode('utf-8')
            if not data:
                return
                
            request = json.loads(data)
            action = request.get("action")
            
            if action == "register":
                response = self._register_peer(request)
            elif action == "discover":
                response = self._discover_peers(request)
            elif action == "unregister":
                response = self._unregister_peer(request)
            elif action == "heartbeat":
                response = self._heartbeat(request)
            else:
                response = {"status": "error", "message": "Unknown action"}
            
            client_socket.sendall(json.dumps(response).encode('utf-8'))
            
        except json.JSONDecodeError:
            error_response = {"status": "error", "message": "Invalid JSON"}
            client_socket.sendall(json.dumps(error_response).encode('utf-8'))
        except Exception as e:
            print(f"[v0] Error handling client {address}: {e}")
        finally:
            client_socket.close()
    
    def _register_peer(self, request):
        """Register a new peer"""
        username = request.get("username")
        ip = request.get("ip")
        port = request.get("port")
        
        if not all([username, ip, port]):
            return {"status": "error", "message": "Missing required fields"}
        
        with self.lock:
            if username in self.peers:
                return {"status": "error", "message": "Username already taken"}
            
            self.peers[username] = {
                "address": (ip, port),
                "last_seen": datetime.now()
            }
            
        print(f"[v0] Registered peer: {username} at {ip}:{port}")
        return {"status": "success", "message": "Peer registered"}
    
    def _discover_peers(self, request):
        """Return list of active peers"""
        with self.lock:
            peers_list = [
                {
                    "username": username,
                    "ip": info["address"][0],
                    "port": info["address"][1]
                }
                for username, info in self.peers.items()
            ]
        
        return {"status": "success", "peers": peers_list}
    
    def _unregister_peer(self, request):
        """Unregister a peer"""
        username = request.get("username")
        
        with self.lock:
            if username in self.peers:
                del self.peers[username]
                print(f"[v0] Unregistered peer: {username}")
                return {"status": "success", "message": "Peer unregistered"}
        
        return {"status": "error", "message": "Peer not found"}
    
    def _heartbeat(self, request):
        """Update peer's last seen timestamp"""
        username = request.get("username")
        
        with self.lock:
            if username in self.peers:
                self.peers[username]["last_seen"] = datetime.now()
                return {"status": "success"}
        
        return {"status": "error", "message": "Peer not found"}
    
    def _cleanup_stale_peers(self):
        """Periodically remove inactive peers"""
        while self.running:
            time.sleep(self.cleanup_interval)
            
            with self.lock:
                current_time = datetime.now()
                stale_peers = [
                    username
                    for username, info in self.peers.items()
                    if (current_time - info["last_seen"]).total_seconds() > self.peer_timeout
                ]
                
                for username in stale_peers:
                    del self.peers[username]
                    print(f"[v0] Removed stale peer: {username}")
    
    def stop(self):
        """Stop the discovery server"""
        self.running = False
        try:
            self.server_socket.close()
        except:
            pass

if __name__ == "__main__":
    server = DiscoveryServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[v0] Shutting down discovery server...")
        server.stop()
