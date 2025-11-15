"""
Secure Chat Client with TLS Encryption
Implements TLS connection, message handling, file transfer, and user interface
"""
import socket
import ssl
import json
import threading
import sys
import os
import base64
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
        self.download_dir = 'downloads'
        self.received_files = []  # Track received files with metadata
        
        # Create downloads directory if it doesn't exist
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
        
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
                chunk = self.socket.recv(min(8192, message_len - len(data)))
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
            print(f"\n[{msg['timestamp']}] {msg['username']}: {msg['content']}")
            self.show_prompt()

        elif msg_type == 'system':
            print(f"\n[*] {msg['message']}")
            self.show_prompt()

        elif msg_type == 'room_changed':
            self.current_room = msg.get('room')
            room_message = msg.get('message')
            print(f"\n[✓] {room_message}")
            self.show_prompt()

        elif msg_type == 'room_list':
            rooms = msg.get('rooms', [])
            print(f"\n[*] Available rooms: {', '.join(rooms)}")
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
        
        elif msg_type == 'file_offer':
            from_user = msg['from']
            filename = msg['filename']
            filesize = msg['filesize']
            file_id = msg['file_id']
            is_broadcast = msg.get('broadcast', False)
            
            if is_broadcast:
                print(f"\n[📁] Broadcast file from {from_user}: {filename} ({filesize} bytes)")
            else:
                print(f"\n[📁] File offer from {from_user}: {filename} ({filesize} bytes)")
            print(f"[*] Type '/accept {file_id}' to download or '/reject {file_id}' to decline")
            self.show_prompt()
        
        elif msg_type == 'file_transfer':
            filename = msg['filename']
            filedata = msg['data']
            from_user = msg['from']
            
            # Decode base64 and save file
            try:
                file_bytes = base64.b64decode(filedata)
                filepath = os.path.join(self.download_dir, filename)
                
                # Add number suffix if file exists
                base, ext = os.path.splitext(filename)
                counter = 1
                original_filepath = filepath
                while os.path.exists(filepath):
                    filepath = os.path.join(self.download_dir, f"{base}_{counter}{ext}")
                    counter += 1
                
                with open(filepath, 'wb') as f:
                    f.write(file_bytes)
                
                # Track received file
                import datetime
                file_info = {
                    'filename': os.path.basename(filepath),
                    'filepath': filepath,
                    'from': from_user,
                    'size': len(file_bytes),
                    'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                self.received_files.append(file_info)
                
                print(f"\n[✓] File received from {from_user}: {filename}")
                print(f"[*] Saved to: {filepath}")
            except Exception as e:
                print(f"\n[!] Error saving file: {e}")
            
            self.show_prompt()
        
        elif msg_type == 'file_rejected':
            print(f"\n[*] {msg['target']} rejected your file transfer")
            self.show_prompt()
    
    def show_prompt(self):
        if self.connected:
            sys.stdout.write(f"[{self.current_room}] > ")
            sys.stdout.flush()
    
    def show_help(self):
        print("\n" + "="*60)
        print("SECURE CHAT CLIENT - Commands")
        print("="*60)
        print("/help                    - Show this help message")
        print("/rooms                   - List available rooms")
        print("/create <room>           - Create a new room")
        print("/join <room>             - Join a room")
        print("/users                   - List users in current room")
        print("/pm <user> <msg>         - Send private message")
        print("/sendfile <user> <path>  - Send file to specific user")
        print("/broadcast <path>        - Broadcast file to all in room")
        print("/sendmulti <u1,u2> <path> - Send file to multiple users")
        print("/accept <file_id>        - Accept file transfer")
        print("/reject <file_id>        - Reject file transfer")
        print("/files                   - List received files")
        print("/view <filename>         - View text file content")
        print("/quit                    - Disconnect and exit")
        print("="*60)
        self.show_prompt()
    
    def handle_command(self, cmd: str):
        # Split only on first space to get command
        parts = cmd.split(maxsplit=1)
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        
        if command == "/quit":
            return False
        
        elif command == "/pm":
            # Split args into target and message (maxsplit=1 for target, rest is message)
            pm_parts = args.split(maxsplit=1)
            if len(pm_parts) == 2:
                self.send_message({
                    'type': 'private_message',
                    'target': pm_parts[0],
                    'content': pm_parts[1]
                })
            else:
                print("[!] Usage: /pm <user> <message>")
                self.show_prompt()
        
        elif command == "/users":
            self.send_message({'type': 'list_users'})
        
        elif command == "/join":
            if args:
                self.send_message({'type': 'join_room', 'room_name': args.strip()})
            else:
                print("[!] Usage: /join <room>")
                self.show_prompt()
        
        elif command == "/create":
            if args:
                self.send_message({'type': 'create_room', 'room_name': args.strip()})
            else:
                print("[!] Usage: /create <room>")
                self.show_prompt()
        
        elif command == "/rooms":
            self.send_message({'type': 'list_rooms'})

        elif command == "/help":
            self.show_help()
        
        elif command == "/sendfile":
            # Split into target and filepath
            file_parts = args.split(maxsplit=1)
            if len(file_parts) == 2:
                target_user = file_parts[0]
                filepath = file_parts[1]
                self.send_file([target_user], filepath)
            else:
                print("[!] Usage: /sendfile <user> <filepath>")
                self.show_prompt()
        
        elif command == "/broadcast":
            if args:
                filepath = args.strip()
                self.send_file([], filepath, broadcast=True)
            else:
                print("[!] Usage: /broadcast <filepath>")
                self.show_prompt()
        
        elif command == "/sendmulti":
            # Split into users and filepath
            multi_parts = args.split(maxsplit=1)
            if len(multi_parts) == 2:
                users_str = multi_parts[0]
                filepath = multi_parts[1]
                target_users = [u.strip() for u in users_str.split(',')]
                self.send_file(target_users, filepath)
            else:
                print("[!] Usage: /sendmulti <user1,user2,...> <filepath>")
                self.show_prompt()
        
        elif command == "/accept":
            if args:
                file_id = args.strip()
                self.send_message({
                    'type': 'file_accept',
                    'file_id': file_id
                })
            else:
                print("[!] Usage: /accept <file_id>")
                self.show_prompt()
        
        elif command == "/reject":
            if args:
                file_id = args.strip()
                self.send_message({
                    'type': 'file_reject',
                    'file_id': file_id
                })
            else:
                print("[!] Usage: /reject <file_id>")
                self.show_prompt()
        
        elif command == "/files":
            self.list_received_files()
        
        elif command == "/view":
            if args:
                filename = args.strip()
                self.view_file(filename)
            else:
                print("[!] Usage: /view <filename>")
                self.show_prompt()
        
        else:
            print("[!] Unknown command")
            print("[*] Use /help")
            self.show_prompt()
        
        return True
    
    def send_file(self, target_users: list, filepath: str, broadcast: bool = False):
        """Send file to specific users or broadcast to room"""
        try:
            if not os.path.exists(filepath):
                print(f"[!] File not found: {filepath}")
                self.show_prompt()
                return
            
            filesize = os.path.getsize(filepath)
            max_size = 10 * 1024 * 1024  # 10MB limit
            
            if filesize > max_size:
                print(f"[!] File too large. Maximum size is {max_size / (1024*1024)}MB")
                self.show_prompt()
                return
            
            # Check if user is trying to send to themselves
            if not broadcast and self.username in target_users:
                print("[!] Cannot send file to yourself")
                self.show_prompt()
                return
            
            filename = os.path.basename(filepath)
            
            with open(filepath, 'rb') as f:
                filedata = f.read()
            
            # Encode to base64 for JSON transmission
            encoded_data = base64.b64encode(filedata).decode('utf-8')
            
            if broadcast:
                print(f"[*] Broadcasting file {filename} ({filesize} bytes) to room...")
                self.send_message({
                    'type': 'file_broadcast',
                    'filename': filename,
                    'filesize': filesize,
                    'data': encoded_data
                })
            else:
                if len(target_users) == 1:
                    print(f"[*] Sending file {filename} ({filesize} bytes) to {target_users[0]}...")
                else:
                    print(f"[*] Sending file {filename} ({filesize} bytes) to {len(target_users)} users...")
                
                self.send_message({
                    'type': 'file_send',
                    'targets': target_users,
                    'filename': filename,
                    'filesize': filesize,
                    'data': encoded_data
                })
            
        except Exception as e:
            print(f"[!] Error sending file: {e}")
            self.show_prompt()
    
    def list_received_files(self):
        """List all received files"""
        if not self.received_files:
            print("\n[*] No files received yet")
            self.show_prompt()
            return
        
        print("\n" + "="*70)
        print("RECEIVED FILES")
        print("="*70)
        print(f"{'#':<4} {'Filename':<25} {'From':<15} {'Size':<10} {'Date'}")
        print("-"*70)
        
        for idx, file_info in enumerate(self.received_files, 1):
            size_str = self.format_size(file_info['size'])
            print(f"{idx:<4} {file_info['filename']:<25} {file_info['from']:<15} {size_str:<10} {file_info['timestamp']}")
        
        print("="*70)
        self.show_prompt()
    
    def format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}TB"
    
    def view_file(self, filename: str):
        """View content of a text file"""
        # Find file in received files
        file_path = None
        for file_info in self.received_files:
            if file_info['filename'] == filename:
                file_path = file_info['filepath']
                break
        
        if not file_path:
            # Try direct path in downloads folder
            file_path = os.path.join(self.download_dir, filename)
            if not os.path.exists(file_path):
                print(f"\n[!] File not found: {filename}")
                print("[*] Use /files to see available files")
                self.show_prompt()
                return
        
        try:
            # Try to read as text
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print("\n" + "="*70)
            print(f"FILE CONTENT: {filename}")
            print("="*70)
            print(content)
            print("="*70)
            
        except UnicodeDecodeError:
            print(f"\n[!] Cannot display {filename} - binary file")
            print("[*] Use an appropriate application to open this file")
        except Exception as e:
            print(f"\n[!] Error reading file: {e}")
        
        self.show_prompt()
    
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
            for _ in range(20):
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
                    self.send_message({'type': 'message', 'content': text})
        
        except KeyboardInterrupt:
            print("\n[*] Interrupted by user")
        
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