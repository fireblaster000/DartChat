"""
P2P Client Module
Implements secure peer-to-peer communication with TLS encryption
"""
import socket
import ssl
import threading
import json
import time
from datetime import datetime

class P2PClient:
    """
    P2P Chat Client with TLS encryption and secure message exchange
    """
    
    def __init__(self, username, listen_port, cert_path, key_path, discovery_server):
        self.username = username
        self.listen_port = listen_port
        self.cert_path = cert_path
        self.key_path = key_path
        self.discovery_server = discovery_server
        
        self.running = False
        self.connections = {}  # {username: socket}
        self.message_callbacks = []
        self.connection_callbacks = []
        
        # TLS context for server (accepting connections)
        self.server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.server_context.load_cert_chain(cert_path, key_path)
        self.server_context.check_hostname = False
        self.server_context.verify_mode = ssl.CERT_NONE  # Self-signed certs
        
        # TLS context for client (making connections)
        self.client_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.client_context.check_hostname = False
        self.client_context.verify_mode = ssl.CERT_NONE  # Self-signed certs
        
    def start(self):
        """Start the P2P client"""
        self.running = True
        
        # Register with discovery server
        if not self._register_with_discovery():
            print("[v0] Failed to register with discovery server")
            return False
        
        # Start listening for incoming connections
        listen_thread = threading.Thread(target=self._listen_for_connections, daemon=True)
        listen_thread.start()
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self._send_heartbeat, daemon=True)
        heartbeat_thread.start()
        
        print(f"[v0] P2P client started for user: {self.username}")
        return True
    
    def _register_with_discovery(self):
        """Register with the discovery server"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.discovery_server)
            
            # Get local IP
            local_ip = self._get_local_ip()
            
            request = {
                "action": "register",
                "username": self.username,
                "ip": local_ip,
                "port": self.listen_port
            }
            
            sock.sendall(json.dumps(request).encode('utf-8'))
            response = json.loads(sock.recv(4096).decode('utf-8'))
            sock.close()
            
            if response.get("status") == "success":
                print(f"[v0] Registered with discovery server")
                return True
            else:
                print(f"[v0] Registration failed: {response.get('message')}")
                return False
                
        except Exception as e:
            print(f"[v0] Error registering with discovery server: {e}")
            return False
    
    def _get_local_ip(self):
        """Get local IP address"""
        try:
            # Connect to external address to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return "127.0.0.1"
    
    def _listen_for_connections(self):
        """Listen for incoming P2P connections"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("0.0.0.0", self.listen_port))
        server_socket.listen(5)
        
        print(f"[v0] Listening for P2P connections on port {self.listen_port}")
        
        while self.running:
            try:
                client_socket, address = server_socket.accept()
                
                # Wrap with TLS
                try:
                    secure_socket = self.server_context.wrap_socket(
                        client_socket,
                        server_side=True
                    )
                    
                    thread = threading.Thread(
                        target=self._handle_peer_connection,
                        args=(secure_socket, address),
                        daemon=True
                    )
                    thread.start()
                    
                except ssl.SSLError as e:
                    print(f"[v0] TLS handshake failed with {address}: {e}")
                    client_socket.close()
                    
            except Exception as e:
                if self.running:
                    print(f"[v0] Error accepting connection: {e}")
        
        server_socket.close()
    
    def _handle_peer_connection(self, secure_socket, address):
        """Handle incoming peer connection"""
        try:
            # Receive handshake
            data = secure_socket.recv(4096).decode('utf-8')
            handshake = json.loads(data)
            
            if handshake.get("type") != "handshake":
                secure_socket.close()
                return
            
            peer_username = handshake.get("username")
            
            # Send handshake response
            response = {
                "type": "handshake_ack",
                "username": self.username
            }
            secure_socket.sendall(json.dumps(response).encode('utf-8'))
            
            # Store connection
            self.connections[peer_username] = secure_socket
            
            print(f"[v0] Established secure connection with {peer_username}")
            self._notify_connection(peer_username, connected=True)
            
            # Handle messages from this peer
            while self.running:
                try:
                    data = secure_socket.recv(4096).decode('utf-8')
                    if not data:
                        break
                    
                    message = json.loads(data)
                    self._handle_message(peer_username, message)
                    
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"[v0] Error receiving from {peer_username}: {e}")
                    break
                    
        except Exception as e:
            print(f"[v0] Error handling peer connection: {e}")
        finally:
            if peer_username in self.connections:
                del self.connections[peer_username]
                self._notify_connection(peer_username, connected=False)
            secure_socket.close()
    
    def connect_to_peer(self, peer_username, peer_ip, peer_port):
        """Establish connection to a peer"""
        if peer_username in self.connections:
            print(f"[v0] Already connected to {peer_username}")
            return True
        
        try:
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((peer_ip, peer_port))
            
            # Wrap with TLS
            secure_socket = self.client_context.wrap_socket(
                sock,
                server_hostname=peer_ip
            )
            
            # Send handshake
            handshake = {
                "type": "handshake",
                "username": self.username
            }
            secure_socket.sendall(json.dumps(handshake).encode('utf-8'))
            
            # Receive handshake response
            response = json.loads(secure_socket.recv(4096).decode('utf-8'))
            
            if response.get("type") != "handshake_ack":
                secure_socket.close()
                return False
            
            # Store connection
            self.connections[peer_username] = secure_socket
            
            print(f"[v0] Connected to {peer_username} at {peer_ip}:{peer_port}")
            self._notify_connection(peer_username, connected=True)
            
            # Start receiving thread
            thread = threading.Thread(
                target=self._receive_messages,
                args=(peer_username, secure_socket),
                daemon=True
            )
            thread.start()
            
            return True
            
        except Exception as e:
            print(f"[v0] Failed to connect to {peer_username}: {e}")
            return False
    
    def _receive_messages(self, peer_username, secure_socket):
        """Receive messages from a connected peer"""
        while self.running and peer_username in self.connections:
            try:
                data = secure_socket.recv(4096).decode('utf-8')
                if not data:
                    break
                
                message = json.loads(data)
                self._handle_message(peer_username, message)
                
            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"[v0] Error receiving from {peer_username}: {e}")
                break
        
        if peer_username in self.connections:
            del self.connections[peer_username]
            self._notify_connection(peer_username, connected=False)
    
    def send_message(self, peer_username, message_text):
        """Send a message to a peer"""
        if peer_username not in self.connections:
            print(f"[v0] Not connected to {peer_username}")
            return False
        
        try:
            message = {
                "type": "chat",
                "from": self.username,
                "text": message_text,
                "timestamp": datetime.now().isoformat()
            }
            
            secure_socket = self.connections[peer_username]
            secure_socket.sendall(json.dumps(message).encode('utf-8'))
            return True
            
        except Exception as e:
            print(f"[v0] Error sending message to {peer_username}: {e}")
            return False
    
    def _handle_message(self, peer_username, message):
        """Handle received message"""
        msg_type = message.get("type")
        
        if msg_type == "chat":
            self._notify_message(peer_username, message.get("text"), message.get("timestamp"))
    
    def discover_peers(self):
        """Discover available peers from discovery server"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.discovery_server)
            
            request = {"action": "discover"}
            sock.sendall(json.dumps(request).encode('utf-8'))
            
            response = json.loads(sock.recv(4096).decode('utf-8'))
            sock.close()
            
            if response.get("status") == "success":
                peers = [p for p in response.get("peers", []) if p["username"] != self.username]
                return peers
            
        except Exception as e:
            print(f"[v0] Error discovering peers: {e}")
        
        return []
    
    def _send_heartbeat(self):
        """Send periodic heartbeat to discovery server"""
        while self.running:
            time.sleep(20)
            
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(self.discovery_server)
                
                request = {
                    "action": "heartbeat",
                    "username": self.username
                }
                
                sock.sendall(json.dumps(request).encode('utf-8'))
                sock.recv(4096)  # Acknowledgment
                sock.close()
                
            except Exception as e:
                print(f"[v0] Heartbeat failed: {e}")
    
    def on_message(self, callback):
        """Register callback for incoming messages"""
        self.message_callbacks.append(callback)
    
    def on_connection_change(self, callback):
        """Register callback for connection status changes"""
        self.connection_callbacks.append(callback)
    
    def _notify_message(self, peer_username, text, timestamp):
        """Notify message callbacks"""
        for callback in self.message_callbacks:
            try:
                callback(peer_username, text, timestamp)
            except Exception as e:
                print(f"[v0] Error in message callback: {e}")
    
    def _notify_connection(self, peer_username, connected):
        """Notify connection callbacks"""
        for callback in self.connection_callbacks:
            try:
                callback(peer_username, connected)
            except Exception as e:
                print(f"[v0] Error in connection callback: {e}")
    
    def stop(self):
        """Stop the P2P client"""
        self.running = False
        
        # Unregister from discovery server
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.discovery_server)
            
            request = {
                "action": "unregister",
                "username": self.username
            }
            
            sock.sendall(json.dumps(request).encode('utf-8'))
            sock.close()
            
        except:
            pass
        
        # Close all connections
        for peer_username, secure_socket in list(self.connections.items()):
            try:
                secure_socket.close()
            except:
                pass
        
        self.connections.clear()
