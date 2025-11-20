"""
Secure Chat Server with TLS Encryption and Voice Call Support
Implements multi-client support, chat rooms, file transfer, voice calls, and secure communication
"""
import socket
import ssl
import threading
import json
import datetime
import re
import uuid
from typing import Dict, Set, Optional
import sys
import signal

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
        if len(self.message_history) > 100:
            self.message_history.pop(0)

class SecureChatServer:
    """TLS-enabled multi-client chat server with voice call support"""
    
    def __init__(self, host: str = '0.0.0.0', port: int = 9999):
        self.host = host
        self.port = port
        self.clients: Dict[socket.socket, dict] = {}
        self.clients_lock = threading.Lock()
        self.rooms: Dict[str, ChatRoom] = {'general': ChatRoom('general')}
        self.username_map: Dict[str, socket.socket] = {}
        self.running = False
        self.server_socket = None
        
        # File transfer tracking
        self.pending_files: Dict[str, dict] = {}
        
        # Voice call tracking
        self.active_calls: Dict[str, dict] = {}  # username -> call info
        
    def validate_username(self, username: str):
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
    
    def get_user_room(self, username: str) -> Optional[str]:
        """Get the room a user is currently in"""
        with self.clients_lock:
            for client, info in self.clients.items():
                if info['username'] == username:
                    return info['room']
        return None
    
    def get_user_address(self, username: str) -> Optional[tuple]:
        """Get the IP address of a user"""
        with self.clients_lock:
            for client, info in self.clients.items():
                if info['username'] == username:
                    return info['address']
        return None
    
    def create_ssl_context(self) -> ssl.SSLContext:
        """Create and configure SSL context for TLS encryption"""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain('certs/server.crt', 'certs/server.key')
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM")
        return context
    
    def broadcast_message(self, message: dict, room: str, exclude_client: Optional[socket.socket] = None):
        """Broadcast message to all clients in a room"""
        with self.clients_lock:
            clients_to_send = []
            for client, info in list(self.clients.items()):
                if info['room'] == room and client != exclude_client:
                    clients_to_send.append(client)

        for client in clients_to_send:
            try:
                self.send_message(client, message)
            except Exception as e:
                print(f"[!] Error sending to client: {e}")
    
    def send_message(self, client: socket.socket, message: dict):
        """Send JSON message to client"""
        data = json.dumps(message).encode('utf-8')
        client.sendall(len(data).to_bytes(4, byteorder='big') + data)
    
    def receive_message(self, client: socket.socket):
        """Receive JSON message from client"""
        try:
            length_bytes = client.recv(4)
            if not length_bytes:
                return None
            
            message_length = int.from_bytes(length_bytes, byteorder='big')
            data = b''
            
            while len(data) < message_length:
                chunk = client.recv(min(8192, message_length - len(data)))
                if not chunk:
                    return None
                data += chunk
            
            return json.loads(data.decode('utf-8'))
        
        except (ConnectionResetError, ConnectionAbortedError, ssl.SSLError):
            return None
        except Exception:
            return None
    
    def handle_client(self, client: socket.socket, address: tuple):
        """Handle individual client connection"""
        username = None
        
        try:
            self.send_message(client, {
                'type': 'auth_request',
                'message': 'Please provide your username'
            })
            
            auth_msg = self.receive_message(client)
            if not auth_msg or auth_msg.get('type') != 'auth':
                return
            
            username = auth_msg.get('username', '').strip()
            ok, msg = self.validate_username(username)
            if not ok:
                self.send_message(client, {'type': 'auth_error', 'message': msg})
                return
            
            with self.clients_lock:
                self.clients[client] = {
                    'username': username,
                    'address': address,
                    'room': 'general'
                }
                self.username_map[username] = client
                self.rooms['general'].add_member(username)
            
            self.send_message(client, {
                'type': 'auth_success',
                'username': username,
                'room': 'general'
            })
            
            print(f"[+] {username} connected from {address[0]}:{address[1]}")
            
            self.broadcast_message({
                'type': 'system',
                'message': f"{username} joined the chat"
            }, 'general', exclude_client=client)
            
            self.send_message(client, {
                'type': 'room_list',
                'rooms': list(self.rooms.keys())
            })
            
            while self.running:
                message = self.receive_message(client)
                if not message:
                    break
                self.process_message(client, message)
        
        finally:
            self.disconnect_client(client, username)
    
    def process_message(self, client: socket.socket, message: dict):
        """Process messages"""
        msg_type = message.get('type')
        
        with self.clients_lock:
            if client not in self.clients:
                return
            username = self.clients[client]['username']
            current_room = self.clients[client]['room']
        
        if msg_type == 'message':
            content = message.get('content', '').strip()
            if content:
                self.rooms[current_room].add_message(username, content)
                self.broadcast_message({
                    'type': 'message',
                    'username': username,
                    'content': content,
                    'timestamp': datetime.datetime.now().strftime("%H:%M:%S")
                }, current_room)

        elif msg_type == 'list_users':
            users = list(self.rooms[current_room].members)
            self.send_message(client, {
                'type': 'user_list',
                'room': current_room,
                'users': users
            })

        elif msg_type == 'list_rooms':
            self.send_message(client, {
                'type': 'room_list',
                'rooms': list(self.rooms.keys())
            })

        elif msg_type == 'private_message':
            target = message.get('target')
            content = message.get('content')
            if target in self.username_map:
                t = self.username_map[target]
                self.send_message(t, {
                    'type': 'private_message',
                    'from': username,
                    'content': content,
                    'timestamp': datetime.datetime.now().strftime("%H:%M:%S")
                })
                self.send_message(client, {
                    'type': 'private_sent',
                    'to': target,
                    'content': content
                })
            else:
                self.send_message(client, {
                    'type': 'system',
                    'message': f"User '{target}' not found"
                })

        elif msg_type == 'create_room':
            room_name = message.get('room_name', '').strip()
            if room_name and room_name not in self.rooms:
                self.rooms[room_name] = ChatRoom(room_name)
                self.send_message(client, {
                    'type': 'system',
                    'message': f"Room '{room_name}' created"
                })
                self.send_message(client, {
                    'type': 'room_list',
                    'rooms': list(self.rooms.keys())
                })
            else:
                self.send_message(client, {
                    'type': 'system',
                    'message': f"Room '{room_name}' already exists"
                })

        elif msg_type == 'join_room':
            room_name = message.get('room_name', '').strip()
            if room_name in self.rooms:
                old_room = current_room
                self.rooms[old_room].remove_member(username)
                self.broadcast_message({
                    'type': 'system',
                    'message': f"{username} left the room"
                }, old_room)

                with self.clients_lock:
                    self.clients[client]['room'] = room_name

                self.rooms[room_name].add_member(username)
                self.send_message(client, {
                    'type': 'room_changed',
                    'room': room_name,
                    'message': f"Joined room '{room_name}'"
                })
                self.broadcast_message({
                    'type': 'system',
                    'message': f"{username} joined the room"
                }, room_name, exclude_client=client)
            else:
                self.send_message(client, {
                    'type': 'system',
                    'message': f"Room '{room_name}' does not exist"
                })
        
        elif msg_type == 'file_send':
            targets = message.get('targets', [])
            filename = message.get('filename')
            filesize = message.get('filesize')
            filedata = message.get('data')
            
            if not targets:
                self.send_message(client, {
                    'type': 'system',
                    'message': 'No target users specified'
                })
                return
            
            targets = [t for t in targets if t != username]
            
            if not targets:
                self.send_message(client, {
                    'type': 'system',
                    'message': 'Cannot send file to yourself'
                })
                return
            
            invalid_users = [t for t in targets if t not in self.username_map]
            if invalid_users:
                self.send_message(client, {
                    'type': 'system',
                    'message': f"User(s) not found: {', '.join(invalid_users)}"
                })
                return
            
            not_in_room = []
            valid_targets = []
            
            for target in targets:
                target_room = self.get_user_room(target)
                if target_room != current_room:
                    not_in_room.append(f"{target} (in #{target_room})")
                else:
                    valid_targets.append(target)
            
            if not_in_room:
                self.send_message(client, {
                    'type': 'system',
                    'message': f"Cannot send file - user(s) not in #{current_room}: {', '.join(not_in_room)}"
                })
            
            if not valid_targets:
                return
            
            for target in valid_targets:
                file_id = str(uuid.uuid4())[:8]
                
                self.pending_files[file_id] = {
                    'from': username,
                    'to': target,
                    'filename': filename,
                    'filesize': filesize,
                    'data': filedata,
                    'broadcast': False
                }
                
                target_client = self.username_map[target]
                self.send_message(target_client, {
                    'type': 'file_offer',
                    'from': username,
                    'filename': filename,
                    'filesize': filesize,
                    'file_id': file_id,
                    'broadcast': False
                })
            
            if len(valid_targets) == 1:
                print(f"[📁] File transfer: {username} -> {valid_targets[0]} ({filename}, {filesize} bytes)")
                self.send_message(client, {
                    'type': 'system',
                    'message': f"Sending {filename} to {valid_targets[0]}..."
                })
            else:
                print(f"[📁] File transfer: {username} -> {len(valid_targets)} users ({filename}, {filesize} bytes)")
                self.send_message(client, {
                    'type': 'system',
                    'message': f"Sending {filename} to {len(valid_targets)} users..."
                })
        
        elif msg_type == 'file_broadcast':
            filename = message.get('filename')
            filesize = message.get('filesize')
            filedata = message.get('data')
            
            with self.clients_lock:
                room_members = [
                    (info['username'], client_sock) 
                    for client_sock, info in self.clients.items() 
                    if info['room'] == current_room and info['username'] != username
                ]
            
            if not room_members:
                self.send_message(client, {
                    'type': 'system',
                    'message': 'No other users in room to broadcast to'
                })
                return
            
            for target_username, target_client in room_members:
                file_id = str(uuid.uuid4())[:8]
                
                self.pending_files[file_id] = {
                    'from': username,
                    'to': target_username,
                    'filename': filename,
                    'filesize': filesize,
                    'data': filedata,
                    'broadcast': True
                }
                
                self.send_message(target_client, {
                    'type': 'file_offer',
                    'from': username,
                    'filename': filename,
                    'filesize': filesize,
                    'file_id': file_id,
                    'broadcast': True
                })
            
            print(f"[📁] File broadcast: {username} -> {current_room} ({filename}, {filesize} bytes, {len(room_members)} recipients)")
            
            self.send_message(client, {
                'type': 'system',
                'message': f"Broadcasting {filename} to {len(room_members)} users in #{current_room}"
            })
        
        elif msg_type == 'file_accept':
            file_id = message.get('file_id')
            
            if file_id not in self.pending_files:
                self.send_message(client, {
                    'type': 'system',
                    'message': 'File offer expired or not found'
                })
                return
            
            file_info = self.pending_files[file_id]
            
            if file_info['to'] != username:
                return
            
            self.send_message(client, {
                'type': 'file_transfer',
                'from': file_info['from'],
                'filename': file_info['filename'],
                'data': file_info['data']
            })
            
            if file_info['from'] in self.username_map:
                sender_client = self.username_map[file_info['from']]
                self.send_message(sender_client, {
                    'type': 'system',
                    'message': f"{username} accepted your file: {file_info['filename']}"
                })
            
            del self.pending_files[file_id]
            print(f"[✓] File transfer completed: {file_info['filename']}")
        
        elif msg_type == 'file_reject':
            file_id = message.get('file_id')
            
            if file_id not in self.pending_files:
                return
            
            file_info = self.pending_files[file_id]
            
            if file_info['to'] != username:
                return
            
            if file_info['from'] in self.username_map:
                sender_client = self.username_map[file_info['from']]
                self.send_message(sender_client, {
                    'type': 'file_rejected',
                    'target': username,
                    'filename': file_info['filename']
                })
            
            del self.pending_files[file_id]
            print(f"[!] File transfer rejected: {file_info['filename']}")
        
        elif msg_type == 'call_request':
            target = message.get('target')
            caller_voice_port = message.get('voice_port')
            
            # Validate target exists
            if target not in self.username_map:
                self.send_message(client, {
                    'type': 'error',
                    'message': f"User '{target}' not found"
                })
                return
            
            # Check if target is in same room
            target_room = self.get_user_room(target)
            if target_room != current_room:
                self.send_message(client, {
                    'type': 'error',
                    'message': f"Cannot call {target} - they are in room #{target_room}"
                })
                return
            
            # Check if caller is already in a call
            if username in self.active_calls:
                self.send_message(client, {
                    'type': 'error',
                    'message': 'You are already in a call'
                })
                return
            
            # Check if target is already in a call
            if target in self.active_calls:
                self.send_message(client, {
                    'type': 'error',
                    'message': f'{target} is already in a call'
                })
                return
            
            # Get caller's IP address
            caller_address = self.get_user_address(username)
            if not caller_address:
                self.send_message(client, {
                    'type': 'error',
                    'message': 'Could not determine your IP address'
                })
                return
            
            # Store pending call
            self.active_calls[username] = {
                'peer': target,
                'status': 'calling',
                'voice_port': caller_voice_port,
                'ip': caller_address[0]
            }
            
            # Forward call request to target
            target_client = self.username_map[target]
            self.send_message(target_client, {
                'type': 'call_request',
                'from': username,
                'peer_ip': caller_address[0],
                'peer_port': caller_voice_port
            })
            
            print(f"[📞] Call request: {username} -> {target}")
        
        elif msg_type == 'call_accept':
            target = message.get('target')
            receiver_voice_port = message.get('voice_port')
            
            # Validate the call exists
            if target not in self.active_calls:
                self.send_message(client, {
                    'type': 'error',
                    'message': 'No pending call from this user'
                })
                return
            
            call_info = self.active_calls[target]
            if call_info['peer'] != username:
                return
            
            # Get receiver's IP address
            receiver_address = self.get_user_address(username)
            if not receiver_address:
                return
            
            # Update call status
            self.active_calls[username] = {
                'peer': target,
                'status': 'active',
                'voice_port': receiver_voice_port,
                'ip': receiver_address[0]
            }
            self.active_calls[target]['status'] = 'active'
            
            # Notify caller that call was accepted
            if target in self.username_map:
                caller_client = self.username_map[target]
                self.send_message(caller_client, {
                    'type': 'call_accepted',
                    'from': username,
                    'peer_ip': receiver_address[0],
                    'peer_port': receiver_voice_port
                })
            
            print(f"[📞] Call connected: {target} <-> {username}")
        
        elif msg_type == 'call_reject':
            target = message.get('target')
            
            # Clean up call
            if target in self.active_calls:
                del self.active_calls[target]
            
            # Notify caller
            if target in self.username_map:
                caller_client = self.username_map[target]
                self.send_message(caller_client, {
                    'type': 'call_rejected',
                    'from': username
                })
            
            print(f"[📞] Call rejected: {target} -> {username}")
        
        elif msg_type == 'call_end':
            target = message.get('target')
            
            # Clean up both sides of the call
            if username in self.active_calls:
                del self.active_calls[username]
            if target in self.active_calls:
                del self.active_calls[target]
            
            # Notify peer
            if target in self.username_map:
                peer_client = self.username_map[target]
                self.send_message(peer_client, {
                    'type': 'call_ended',
                    'from': username
                })
            
            print(f"[📞] Call ended: {username} <-> {target}")

    def disconnect_client(self, client: socket.socket, username: Optional[str]):
        """Cleanup disconnect"""
        if not username:
            with self.clients_lock:
                if client in self.clients:
                    del self.clients[client]
            try:
                client.close()
            except:
                pass
            return

        print(f"[!] Cleaning up client {username}")
        
        # Clean up any active calls
        if username in self.active_calls:
            call_info = self.active_calls[username]
            peer = call_info['peer']
            
            # Notify peer that call ended
            if peer in self.username_map:
                peer_client = self.username_map[peer]
                try:
                    self.send_message(peer_client, {
                        'type': 'call_ended',
                        'from': username
                    })
                except:
                    pass
            
            # Clean up call info
            del self.active_calls[username]
            if peer in self.active_calls:
                del self.active_calls[peer]
            
            print(f"[📞] Call terminated due to disconnect: {username} <-> {peer}")

        room = None
        with self.clients_lock:
            if client in self.clients:
                room = self.clients[client]['room']
                del self.clients[client]

            if username in self.username_map:
                del self.username_map[username]

        if room and room in self.rooms:
            self.rooms[room].remove_member(username)
            self.broadcast_message({
                'type': 'system',
                'message': f"{username} left the chat"
            }, room)

        print(f"[-] {username} disconnected")

        try:
            client.close()
        except:
            pass
    
    def shutdown(self):
        """Graceful shutdown"""
        print("\n[*] Shutting down server...")
        self.running = False
        
        with self.clients_lock:
            for client in list(self.clients.keys()):
                try:
                    self.send_message(client, {
                        'type': 'system',
                        'message': 'Server is shutting down'
                    })
                    client.close()
                except:
                    pass
            self.clients.clear()
            self.username_map.clear()
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        print("[✓] Server shut down complete")

    def start(self):
        """Start server"""
        self.running = True
        ssl_context = self.create_ssl_context()

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)

        print(f"[✓] Secure Chat Server started on {self.host}:{self.port}")
        print(f"[✓] TLS encryption enabled")
        print(f"[✓] Voice calls enabled (UDP)")
        print(f"[✓] Waiting for connections...")
        print(f"[*] Press Ctrl+C to stop the server\n")

        try:
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    if not self.running:
                        break
                    secure_client = ssl_context.wrap_socket(client_socket, server_side=True)

                    threading.Thread(
                        target=self.handle_client,
                        args=(secure_client, address),
                        daemon=True
                    ).start()
                except OSError:
                    break

        except KeyboardInterrupt:
            print("\n[*] Keyboard interrupt received")

        finally:
            self.shutdown()

def signal_handler(signum, frame):
    """Handle signals for graceful shutdown"""
    print("\n[*] Signal received, shutting down...")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    server = SecureChatServer()
    try:
        server.start()
    except Exception as e:
        print(f"[!] Server error: {e}")
        server.shutdown()
        sys.exit(1)