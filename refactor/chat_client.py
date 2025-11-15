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
        context.check_hostname = False  # self-signed
        context.verify_mode = ssl.CERT_NONE
        
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM")
        
        return context
    
    def send_message(self, message: dict):
        try:
            data = json.dumps(message).encode('utf-8')
            self.socket.sendall(len(data).to_bytes(4, byteorder='big') + data)
        except:
            self.disconnect()
    
    def receive_message(self):
        """Receive message from server"""
        try:
            length_bytes = self.socket.recv(4)
            if not length_bytes:
                return None
            
            message_len = int.from_bytes(length_bytes, 'big')
            data = b''
            while len(data) < message_len:
                chunk = self.socket.recv(message_len - len(data))
                if not chunk:
                    return None
                data += chunk
            
            return json.loads(data.decode('utf-8'))
        
        except:
            return None
    
    def receive_handler(self):
        while self.running:
            msg = self.receive_message()
            if not msg:
                break
            self.process_message(msg)
        
        if self.running:
            print("\n[!] Disconnected from server")
        self.disconnect()
    
    def process_message(self, msg: dict):
        msg_type = msg.get('type')

        if msg_type == 'auth_success':
            self.username = msg["username"]
            self.current_room = msg["room"]
            print(f"\n[✓] Connected as '{self.username}' in room '{self.current_room}'")
            self.connected = True
            self.show_help()

        elif msg_type == 'message':
            # Do NOT show your own message (server excludes you)
            print(f"\n[{msg['timestamp']}] {msg['username']}: {msg['content']}")
            self.show_prompt()

        elif msg_type == 'system':
            print(f"\n[*] {msg['message']}")
            self.show_prompt()

        elif msg_type == 'room_list':
            print("\n[*] Available rooms:", ', '.join(msg['rooms']))
            self.show_prompt()

        elif msg_type == 'user_list':
            print(f"\n[*] Users in {msg['room']}: {', '.join(msg['users'])}")
            self.show_prompt()

        elif msg_type == 'private_message':
            print(f"\n[{msg['timestamp']}] [PM from {msg['from']}]: {msg['content']}")
            self.show_prompt()
        
        elif msg_type == 'private_sent':
            print(f"\n[*] PM sent to {msg['to']}")
            self.show_prompt()
    
    def show_prompt(self):
        if self.connected:
            sys.stdout.write(f"[{self.current_room}] > ")
            sys.stdout.flush()
    
    def show_help(self):
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
        self.show_prompt()
    
    def handle_command(self, cmd: str):
        parts = cmd.split(maxsplit=2)
        if parts[0] == "/quit":
            return False
        
        elif parts[0] == "/pm" and len(parts) == 3:
            self.send_message({
                'type': 'private_message',
                'target': parts[1],
                'content': parts[2]
            })
        
        elif parts[0] == "/users":
            self.send_message({'type': 'list_users'})
        
        elif parts[0] == "/join" and len(parts) == 2:
            self.send_message({'type': 'join_room', 'room_name': parts[1]})
        
        elif parts[0] == "/create" and len(parts) == 2:
            self.send_message({'type': 'create_room', 'room_name': parts[1]})
        
        elif parts[0] == "/rooms":
            self.send_message({'type': 'list_rooms'})

        elif parts[0] == "/help":
            self.show_help()
        
        else:
            print("[!] Unknown command")
            print("[*] Use /help")
            self.show_prompt()
        
        return True
    
    def connect(self, username: str) -> bool:
        try:
            sslctx = self.create_ssl_context()
            raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket = sslctx.wrap_socket(raw, server_hostname=self.host)

            print(f"[*] Connecting to {self.host}:{self.port}...")
            self.socket.connect((self.host, self.port))
            print("[✓] TLS connection established")

            # Wait for server auth_request
            auth_req = self.receive_message()
            if not auth_req or auth_req.get("type") != "auth_request":
                print("[!] Invalid server handshake")
                return False

            # Send our username
            self.send_message({
                "type": "auth",
                "username": username
            })

            # Start receiving thread AFTER sending auth
            self.running = True
            recv_thread = threading.Thread(target=self.receive_handler, daemon=True)
            recv_thread.start()

            # Wait for server to accept username
            import time
            for _ in range(20):   # up to 2 seconds
                if self.connected:
                    return True
                time.sleep(0.1)

            print("[!] Authentication timeout")
            return False

        except Exception as e:
            print(f"[!] Connection failed: {e}")
            return False

    
    def disconnect(self):
        self.running = False
        self.connected = False

        try:
            if self.socket:
                self.socket.close()
        except:
            pass
    
    def run(self):
        try:
            while self.running and self.connected:
                self.show_prompt()
                text = input().strip()
                if not text:
                    continue

                if text.startswith("/"):
                    if not self.handle_command(text):
                        break
                else:
                    # Send message to server but don't echo locally
                    self.send_message({'type': 'message', 'content': text})
        
        finally:
            self.disconnect()
            print("[✓] Disconnected")

def main():
    print("="*60)
    print("SECURE CHAT CLIENT - TLS Encrypted")
    print("="*60)

    host = input("Server address [localhost]: ").strip() or "localhost"
    port = int(input("Server port [9999]: ").strip() or "9999")

    username = input("Enter username: ").strip()

    client = SecureChatClient(host, port)
    if client.connect(username):
        client.run()

if __name__ == "__main__":
    main()