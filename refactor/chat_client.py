"""
Secure Chat Client with TLS Encryption
Implements TLS connection, message handling, and user interface
"""
import socket
import ssl
import json
import threading
import sys
from typing import Optional

class SecureChatClient:
    """TLS-enabled chat client"""
    
    def __init__(self, host: str = 'localhost', port: int = 9999):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.username: Optional[str] = None
        self.current_room = 'general'
        self.running = False
        self.connected = False
        
    def create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for TLS encryption"""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        
        # For self-signed certificates, disable hostname verification
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # Security configurations
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
        
        return context
    
    def send_message(self, message: dict):
        """Send JSON message to server"""
        try:
            data = json.dumps(message).encode('utf-8')
            self.socket.sendall(len(data).to_bytes(4, byteorder='big') + data)
        except Exception as e:
            print(f"\n[!] Error sending message: {e}")
            self.disconnect()
    
    def receive_message(self) -> Optional[dict]:
        """Receive JSON message from server"""
        try:
            # Read message length
            length_bytes = self.socket.recv(4)
            if not length_bytes:
                return None
            
            message_length = int.from_bytes(length_bytes, byteorder='big')
            
            # Read full message
            data = b''
            while len(data) < message_length:
                chunk = self.socket.recv(min(4096, message_length - len(data)))
                if not chunk:
                    return None
                data += chunk
            
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            print(f"\n[!] Error receiving message: {e}")
            return None
    
    def receive_handler(self):
        """Handle incoming messages from server"""
        while self.running:
            try:
                message = self.receive_message()
                if not message:
                    break
                
                self.process_message(message)
            except Exception as e:
                if self.running:
                    print(f"\n[!] Connection error: {e}")
                break
        
        if self.running:
            print("\n[!] Disconnected from server")
            self.disconnect()
    
    def process_message(self, message: dict):
        """Process different message types from server"""
        msg_type = message.get('type')
        
        if msg_type == 'auth_request':
            # Server requesting authentication
            pass  # Handled in connect method
        
        elif msg_type == 'auth_success':
            self.username = message.get('username')
            self.current_room = message.get('room', 'general')
            print(f"\n[✓] Connected as '{self.username}' in room '{self.current_room}'")
            self.connected = True
            self.show_help()
        
        elif msg_type == 'auth_error':
            print(f"\n[!] Authentication error: {message.get('message')}")
            self.disconnect()
        
        elif msg_type == 'message':
            # Regular chat message
            username = message.get('username')
            content = message.get('content')
            timestamp = message.get('timestamp')
            print(f"\n[{timestamp}] {username}: {content}")
            self.show_prompt()
        
        elif msg_type == 'private_message':
            # Private message received
            from_user = message.get('from')
            content = message.get('content')
            timestamp = message.get('timestamp')
            print(f"\n[{timestamp}] [PM from {from_user}]: {content}")
            self.show_prompt()
        
        elif msg_type == 'private_sent':
            # Private message sent confirmation
            to_user = message.get('to')
            content = message.get('content')
            print(f"\n[PM to {to_user}]: {content}")
            self.show_prompt()
        
        elif msg_type == 'system':
            # System message
            print(f"\n[*] {message.get('message')}")
            self.show_prompt()
        
        elif msg_type == 'room_changed':
            self.current_room = message.get('room')
            print(f"\n[✓] Joined room: {self.current_room}")
            self.show_prompt()
        
        elif msg_type == 'room_list':
            rooms = message.get('rooms', [])
            print(f"\n[*] Available rooms: {', '.join(rooms)}")
            self.show_prompt()
        
        elif msg_type == 'user_list':
            room = message.get('room')
            users = message.get('users', [])
            print(f"\n[*] Users in {room}: {', '.join(users)}")
            self.show_prompt()
        
        elif msg_type == 'error':
            print(f"\n[!] Error: {message.get('message')}")
            self.show_prompt()
    
    def show_prompt(self):
        """Show input prompt"""
        if self.connected:
            print(f"[{self.current_room}] > ", end='', flush=True)
    
    def show_help(self):
        """Display available commands"""
        print("\n" + "="*60)
        print("SECURE CHAT CLIENT - Commands")
        print("="*60)
        print("/help               - Show this help message")
        print("/rooms              - List available rooms")
        print("/create <room>      - Create a new room")
        print("/join <room>        - Join a room")
        print("/users              - List users in current room")
        print("/pm <user> <msg>    - Send private message")
        print("/quit               - Disconnect and exit")
        print("="*60)
        print()
        self.show_prompt()
    
    def handle_command(self, command: str) -> bool:
        """Handle client commands"""
        parts = command.split(maxsplit=2)
        cmd = parts[0].lower()
        
        if cmd == '/quit':
            return False
        
        elif cmd == '/help':
            self.show_help()
        
        elif cmd == '/rooms':
            # Request room list (server will send it)
            print("[*] Requesting room list...")
        
        elif cmd == '/create':
            if len(parts) < 2:
                print("[!] Usage: /create <room_name>")
            else:
                room_name = parts[1]
                self.send_message({
                    'type': 'create_room',
                    'room_name': room_name
                })
        
        elif cmd == '/join':
            if len(parts) < 2:
                print("[!] Usage: /join <room_name>")
            else:
                room_name = parts[1]
                self.send_message({
                    'type': 'join_room',
                    'room_name': room_name
                })
        
        elif cmd == '/users':
            self.send_message({
                'type': 'list_users'
            })
        
        elif cmd == '/pm':
            if len(parts) < 3:
                print("[!] Usage: /pm <username> <message>")
            else:
                target = parts[1]
                message = parts[2]
                self.send_message({
                    'type': 'private_message',
                    'target': target,
                    'content': message
                })
        
        else:
            print(f"[!] Unknown command: {cmd}")
            print("[*] Type /help for available commands")
        
        return True
    
    def connect(self, username: str) -> bool:
        """Connect to the server with TLS encryption"""
        try:
            # Create SSL context
            ssl_context = self.create_ssl_context()
            
            # Create socket and wrap with TLS
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket = ssl_context.wrap_socket(raw_socket, server_hostname=self.host)
            
            # Connect to server
            print(f"[*] Connecting to {self.host}:{self.port}...")
            self.socket.connect((self.host, self.port))
            print(f"[✓] TLS connection established")
            print(f"[✓] Cipher: {self.socket.cipher()[0]}")
            print(f"[✓] TLS Version: {self.socket.version()}")
            
            self.running = True
            
            # Wait for auth request
            auth_request = self.receive_message()
            if not auth_request or auth_request.get('type') != 'auth_request':
                print("[!] Invalid server response")
                return False
            
            # Send authentication
            self.send_message({
                'type': 'auth',
                'username': username
            })
            
            # Start receive thread
            receive_thread = threading.Thread(target=self.receive_handler, daemon=True)
            receive_thread.start()
            
            # Wait for authentication response
            import time
            time.sleep(0.5)
            
            return self.connected
            
        except Exception as e:
            print(f"[!] Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from server"""
        self.running = False
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
    
    def run(self):
        """Main client loop"""
        try:
            while self.running and self.connected:
                self.show_prompt()
                user_input = input().strip()
                
                if not user_input:
                    continue
                
                if user_input.startswith('/'):
                    if not self.handle_command(user_input):
                        break
                else:
                    # Send regular message
                    self.send_message({
                        'type': 'message',
                        'content': user_input
                    })
        
        except KeyboardInterrupt:
            print("\n[!] Interrupted by user")
        except EOFError:
            print("\n[!] Input stream closed")
        except Exception as e:
            print(f"\n[!] Error: {e}")
        finally:
            self.disconnect()
            print("\n[✓] Disconnected")

def main():
    """Main entry point"""
    print("="*60)
    print("SECURE CHAT CLIENT - TLS Encrypted")
    print("="*60)
    
    # Get connection details
    host = input("Server address [localhost]: ").strip() or 'localhost'
    port_input = input("Server port [9999]: ").strip()
    port = int(port_input) if port_input else 9999
    
    # Get username
    while True:
        username = input("Enter username (3-20 chars, alphanumeric): ").strip()
        if 3 <= len(username) <= 20:
            break
        print("[!] Username must be 3-20 characters")
    
    # Create and connect client
    client = SecureChatClient(host, port)
    
    if client.connect(username):
        client.run()
    else:
        print("[!] Failed to connect to server")
        sys.exit(1)

if __name__ == "__main__":
    main()
