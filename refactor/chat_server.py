"""
Secure Chat Server with TLS Encryption
Implements multi-client support, chat rooms, and secure communication
"""
import socket
import ssl
import threading
import json
import datetime
import re
from typing import Dict, Set, Optional
import sys

class ChatRoom:
    """Represents a chat room with members"""
    def __init__(self, name: str):
        self.name = name
        self.members: Set[str] = set()
        self.message_history = []
        
    def add_member(self, username: str):
        self.members.add(username)
        
    def remove_member(self, username: str):
        self.members.discard(username)
        
    def add_message(self, username: str, message: str):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.message_history.append({
            'username': username,
            'message': message,
            'timestamp': timestamp
        })
        # Keep only last 100 messages
        if len(self.message_history) > 100:
            self.message_history.pop(0)

class SecureChatServer:
    """TLS-enabled multi-client chat server"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 9999):
        self.host = host
        self.port = port
        self.clients: Dict[socket.socket, dict] = {}
        self.clients_lock = threading.Lock()
        self.rooms: Dict[str, ChatRoom] = {'general': ChatRoom('general')}
        self.username_map: Dict[str, socket.socket] = {}
        self.running = False
        
    def validate_username(self, username: str) -> tuple[bool, str]:
        """Validate username according to security rules"""
        if not username or len(username) < 3:
            return False, "Username must be at least 3 characters"
        if len(username) > 20:
            return False, "Username must be less than 20 characters"
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            return False, "Username can only contain letters, numbers, hyphens, and underscores"
        if username.lower() in [u.lower() for u in self.username_map.keys()]:
            return False, "Username already taken"
        return True, "Valid"
    
    def create_ssl_context(self) -> ssl.SSLContext:
        """Create and configure SSL context for TLS encryption"""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain('certs/server.crt', 'certs/server.key')
        
        # Security configurations
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
        context.options |= ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3 | ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
        
        return context
    
    def broadcast_message(self, message: dict, room: str, exclude_client: Optional[socket.socket] = None):
        """Broadcast message to all clients in a room"""
        with self.clients_lock:
            for client, info in self.clients.items():
                if info['room'] == room and client != exclude_client:
                    try:
                        self.send_message(client, message)
                    except Exception as e:
                        print(f"[!] Error broadcasting to client: {e}")
    
    def send_message(self, client: socket.socket, message: dict):
        """Send JSON message to client"""
        try:
            data = json.dumps(message).encode('utf-8')
            client.sendall(len(data).to_bytes(4, byteorder='big') + data)
        except Exception as e:
            print(f"[!] Error sending message: {e}")
            raise
    
    def receive_message(self, client: socket.socket) -> Optional[dict]:
        """Receive JSON message from client"""
        try:
            # Read message length (4 bytes)
            length_bytes = client.recv(4)
            if not length_bytes:
                return None
            
            message_length = int.from_bytes(length_bytes, byteorder='big')
            
            # Read the full message
            data = b''
            while len(data) < message_length:
                chunk = client.recv(min(4096, message_length - len(data)))
                if not chunk:
                    return None
                data += chunk
            
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            print(f"[!] Error receiving message: {e}")
            return None
    
    def handle_client(self, client: socket.socket, address: tuple):
        """Handle individual client connection"""
        username = None
        
        try:
            # Request username
            self.send_message(client, {
                'type': 'auth_request',
                'message': 'Please provide your username'
            })
            
            # Receive and validate username
            auth_msg = self.receive_message(client)
            if not auth_msg or auth_msg.get('type') != 'auth':
                raise Exception("Invalid authentication")
            
            username = auth_msg.get('username', '').strip()
            is_valid, validation_msg = self.validate_username(username)
            
            if not is_valid:
                self.send_message(client, {
                    'type': 'auth_error',
                    'message': validation_msg
                })
                return
            
            # Add client to the system
            with self.clients_lock:
                self.clients[client] = {
                    'username': username,
                    'address': address,
                    'room': 'general'
                }
                self.username_map[username] = client
                self.rooms['general'].add_member(username)
            
            # Send authentication success
            self.send_message(client, {
                'type': 'auth_success',
                'username': username,
                'room': 'general'
            })
            
            print(f"[+] {username} connected from {address[0]}:{address[1]}")
            
            # Announce to room
            self.broadcast_message({
                'type': 'system',
                'message': f"{username} joined the chat"
            }, 'general', exclude_client=client)
            
            # Send available rooms
            self.send_message(client, {
                'type': 'room_list',
                'rooms': list(self.rooms.keys())
            })
            
            # Main message loop
            while self.running:
                message = self.receive_message(client)
                if not message:
                    break
                
                self.process_message(client, message)
        
        except Exception as e:
            print(f"[!] Error handling client: {e}")
        
        finally:
            self.disconnect_client(client, username)
    
    def process_message(self, client: socket.socket, message: dict):
        """Process different types of messages"""
        msg_type = message.get('type')
        
        with self.clients_lock:
            if client not in self.clients:
                return
            
            client_info = self.clients[client]
            username = client_info['username']
            current_room = client_info['room']
        
        if msg_type == 'message':
            # Regular chat message
            content = message.get('content', '').strip()
            if content:
                # Add to room history
                if current_room in self.rooms:
                    self.rooms[current_room].add_message(username, content)
                
                # Broadcast to room
                self.broadcast_message({
                    'type': 'message',
                    'username': username,
                    'content': content,
                    'timestamp': datetime.datetime.now().strftime("%H:%M:%S")
                }, current_room)
        
        elif msg_type == 'create_room':
            # Create new room
            room_name = message.get('room_name', '').strip()
            if room_name and room_name not in self.rooms:
                if re.match(r'^[a-zA-Z0-9_-]+$', room_name):
                    self.rooms[room_name] = ChatRoom(room_name)
                    self.send_message(client, {
                        'type': 'system',
                        'message': f"Room '{room_name}' created successfully"
                    })
                    # Notify all clients of new room
                    with self.clients_lock:
                        for c in self.clients.keys():
                            self.send_message(c, {
                                'type': 'room_list',
                                'rooms': list(self.rooms.keys())
                            })
                else:
                    self.send_message(client, {
                        'type': 'error',
                        'message': "Invalid room name. Use only letters, numbers, hyphens, and underscores"
                    })
        
        elif msg_type == 'join_room':
            # Join existing room
            room_name = message.get('room_name', '').strip()
            if room_name in self.rooms:
                # Leave current room
                if current_room in self.rooms:
                    self.rooms[current_room].remove_member(username)
                    self.broadcast_message({
                        'type': 'system',
                        'message': f"{username} left the room"
                    }, current_room, exclude_client=client)
                
                # Join new room
                with self.clients_lock:
                    self.clients[client]['room'] = room_name
                self.rooms[room_name].add_member(username)
                
                self.send_message(client, {
                    'type': 'room_changed',
                    'room': room_name
                })
                
                self.broadcast_message({
                    'type': 'system',
                    'message': f"{username} joined the room"
                }, room_name, exclude_client=client)
        
        elif msg_type == 'list_users':
            # List users in current room
            if current_room in self.rooms:
                users = list(self.rooms[current_room].members)
                self.send_message(client, {
                    'type': 'user_list',
                    'room': current_room,
                    'users': users
                })
        
        elif msg_type == 'private_message':
            # Send private message
            target_username = message.get('target')
            content = message.get('content', '').strip()
            
            if target_username in self.username_map and content:
                target_client = self.username_map[target_username]
                self.send_message(target_client, {
                    'type': 'private_message',
                    'from': username,
                    'content': content,
                    'timestamp': datetime.datetime.now().strftime("%H:%M:%S")
                })
                self.send_message(client, {
                    'type': 'private_sent',
                    'to': target_username,
                    'content': content
                })
    
    def disconnect_client(self, client: socket.socket, username: Optional[str]):
        """Clean up client disconnection"""
        with self.clients_lock:
            if client in self.clients:
                client_info = self.clients[client]
                username = client_info['username']
                current_room = client_info['room']
                
                # Remove from room
                if current_room in self.rooms:
                    self.rooms[current_room].remove_member(username)
                    self.broadcast_message({
                        'type': 'system',
                        'message': f"{username} left the chat"
                    }, current_room)
                
                # Remove from tracking
                del self.clients[client]
                if username in self.username_map:
                    del self.username_map[username]
                
                print(f"[-] {username} disconnected")
        
        try:
            client.close()
        except:
            pass
    
    def start(self):
        """Start the server"""
        self.running = True
        
        # Create SSL context
        ssl_context = self.create_ssl_context()
        
        # Create socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        
        print(f"[✓] Secure Chat Server started on {self.host}:{self.port}")
        print(f"[✓] TLS encryption enabled (TLS 1.2+)")
        print(f"[✓] Waiting for connections...\n")
        
        try:
            while self.running:
                try:
                    client_socket, address = server_socket.accept()
                    
                    # Wrap with TLS
                    secure_client = ssl_context.wrap_socket(client_socket, server_side=True)
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(secure_client, address),
                        daemon=True
                    )
                    client_thread.start()
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"[!] Error accepting connection: {e}")
        
        finally:
            self.running = False
            server_socket.close()
            print("\n[✓] Server shut down")

if __name__ == "__main__":
    server = SecureChatServer(host='0.0.0.0', port=9999)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[!] Server interrupted by user")
    except Exception as e:
        print(f"[!] Server error: {e}")
        sys.exit(1)
