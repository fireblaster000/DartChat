"""
Secure Chat Client with TLS Encryption
Enhanced with voice calls, improved file handling, and complete feature set
"""
import socket
import ssl
import json
import threading
import sys
import os
import base64
import struct
import time
from typing import Optional
from datetime import datetime

try:
    import pyaudio
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False
    print("[!] PyAudio not available - voice calls disabled")
    print("[*] Install with: pip install pyaudio")


class VoiceCall:
    """Manages a single voice call session"""
    
    def __init__(self, peer_ip: str, peer_port: int, local_port: int):
        if not VOICE_AVAILABLE:
            raise Exception("PyAudio not available")
        
        # Audio configuration
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100
        
        # Network configuration
        self.peer_ip = peer_ip
        self.peer_port = peer_port
        self.local_port = local_port
        
        # State
        self.is_active = False
        self.is_muted = False
        
        # Audio streams
        self.audio = None
        self.input_stream = None
        self.output_stream = None
        
        # UDP sockets
        self.send_socket = None
        self.recv_socket = None
        
        # Threads
        self.send_thread = None
        self.recv_thread = None
        
    def start(self):
        """Start the voice call"""
        if self.is_active:
            return False
        
        try:
            # Initialize PyAudio
            self.audio = pyaudio.PyAudio()
            
            # Open audio streams
            self.input_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            
            self.output_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK
            )
            
            # Create UDP sockets
            self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            self.recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.recv_socket.bind(('0.0.0.0', self.local_port))
            self.recv_socket.settimeout(0.1)
            
            self.is_active = True
            
            # Start threads
            self.send_thread = threading.Thread(target=self._send_audio, daemon=True)
            self.recv_thread = threading.Thread(target=self._receive_audio, daemon=True)
            
            self.send_thread.start()
            self.recv_thread.start()
            
            return True
            
        except Exception as e:
            print(f"[!] Error starting call: {e}")
            self.stop()
            return False
    
    def _send_audio(self):
        """Capture audio and send via UDP"""
        sequence_number = 0
        
        while self.is_active:
            try:
                if not self.is_muted:
                    data = self.input_stream.read(self.CHUNK, exception_on_overflow=False)
                    packet = struct.pack('I', sequence_number) + data
                    self.send_socket.sendto(packet, (self.peer_ip, self.peer_port))
                    sequence_number += 1
                else:
                    silence = b'\x00' * (self.CHUNK * 2)
                    packet = struct.pack('I', sequence_number) + silence
                    self.send_socket.sendto(packet, (self.peer_ip, self.peer_port))
                    sequence_number += 1
                    time.sleep(0.02)
                    
            except Exception as e:
                if self.is_active:
                    print(f"[!] Send error: {e}")
                break
    
    def _receive_audio(self):
        """Receive audio via UDP and play"""
        while self.is_active:
            try:
                packet, addr = self.recv_socket.recvfrom(4096)
                
                if len(packet) > 4:
                    audio_data = packet[4:]
                    self.output_stream.write(audio_data)
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_active:
                    print(f"[!] Receive error: {e}")
                break
    
    def toggle_mute(self):
        """Toggle microphone mute"""
        self.is_muted = not self.is_muted
        return self.is_muted
    
    def stop(self):
        """Stop the voice call and cleanup resources"""
        if not self.is_active:
            return
        
        self.is_active = False
        
        # Wait for threads
        if self.send_thread and self.send_thread.is_alive():
            self.send_thread.join(timeout=1)
        if self.recv_thread and self.recv_thread.is_alive():
            self.recv_thread.join(timeout=1)
        
        # Close streams
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
        
        if self.audio:
            self.audio.terminate()
        
        # Close sockets
        if self.send_socket:
            self.send_socket.close()
        if self.recv_socket:
            self.recv_socket.close()


class SecureChatClient:
    """TLS-enabled chat client with voice call support"""
    
    def __init__(self, host: str = 'localhost', port: int = 9999):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.username: Optional[str] = None
        self.current_room = 'general'
        self.running = False
        self.connected = False
        self.download_dir = 'downloads'
        self.received_files = []
        self.pending_file_offers = {}
        
        # Voice call variables
        self.active_call: Optional[VoiceCall] = None
        self.call_peer: Optional[str] = None
        self.voice_port = 5000
        
        # Create downloads directory if it doesn't exist
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
        
    def create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for TLS encryption"""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
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
            
            # Store pending offer
            self.pending_file_offers[file_id] = msg
            
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
                while os.path.exists(filepath):
                    filepath = os.path.join(self.download_dir, f"{base}_{counter}{ext}")
                    counter += 1
                
                with open(filepath, 'wb') as f:
                    f.write(file_bytes)
                
                # Track received file
                file_info = {
                    'filename': os.path.basename(filepath),
                    'filepath': filepath,
                    'from': from_user,
                    'size': len(file_bytes),
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                self.received_files.append(file_info)
                
                print(f"\n[✓] File received from {from_user}: {filename}")
                print(f"[*] Saved to: {filepath}")
            except Exception as e:
                print(f"\n[!] Error saving file: {e}")
            
            self.show_prompt()
        
        elif msg_type == 'file_rejected':
            print(f"\n[*] {msg['target']} rejected your file: {msg['filename']}")
            self.show_prompt()
        
        elif msg_type == 'call_request':
            self.handle_call_request(msg)
        
        elif msg_type == 'call_accepted':
            self.handle_call_accepted(msg)
        
        elif msg_type == 'call_rejected':
            print(f"\n[*] {msg['from']} rejected your call")
            self.show_prompt()
        
        elif msg_type == 'call_ended':
            self.handle_call_ended(msg)
        
        elif msg_type == 'error':
            print(f"\n[!] Error: {msg.get('message', 'Unknown error')}")
            self.show_prompt()
    
    def handle_call_request(self, msg: dict):
        """Handle incoming call request"""
        from_user = msg['from']
        peer_ip = msg['peer_ip']
        peer_port = msg['peer_port']
        
        print(f"\n[📞] Incoming call from {from_user}")
        print(f"[*] Type '/answer' to accept or '/decline' to reject")
        
        # Store pending call info
        self.pending_call = {
            'from': from_user,
            'peer_ip': peer_ip,
            'peer_port': peer_port
        }
        
        self.show_prompt()
    
    def handle_call_accepted(self, msg: dict):
        """Handle call acceptance"""
        from_user = msg['from']
        peer_ip = msg['peer_ip']
        peer_port = msg['peer_port']
        
        # Start voice call
        self.call_peer = from_user
        
        try:
            self.active_call = VoiceCall(peer_ip, peer_port, self.voice_port)
            
            if self.active_call.start():
                print(f"\n[📞] {from_user} answered - Call connected!")
                print(f"[*] Type '/mute' to toggle microphone, '/endcall' to hang up")
                self.show_prompt()
            else:
                print(f"\n[!] Failed to start voice call")
                self.active_call = None
                self.call_peer = None
                self.show_prompt()
        except Exception as e:
            print(f"\n[!] Voice call error: {e}")
            self.active_call = None
            self.call_peer = None
            self.show_prompt()
    
    def handle_call_ended(self, msg: dict):
        """Handle call ended by peer"""
        from_user = msg['from']
        
        if self.active_call and self.call_peer == from_user:
            self.active_call.stop()
            self.active_call = None
            self.call_peer = None
            
            print(f"\n[📞] {from_user} ended the call")
            self.show_prompt()
    
    def show_prompt(self):
        if self.connected:
            call_indicator = " [IN CALL]" if self.active_call else ""
            sys.stdout.write(f"[{self.current_room}]{call_indicator} > ")
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
        if VOICE_AVAILABLE:
            print("/call <user>             - Start voice call with user")
            print("/answer                  - Answer incoming call")
            print("/decline                 - Decline incoming call")
            print("/mute                    - Toggle microphone mute")
            print("/endcall                 - End active call")
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
        
        elif command == "/call":
            if not VOICE_AVAILABLE:
                print("[!] Voice calls not available - PyAudio not installed")
                self.show_prompt()
            elif args:
                target = args.strip()
                self.start_call(target)
            else:
                print("[!] Usage: /call <user>")
                self.show_prompt()
        
        elif command == "/answer":
            if not VOICE_AVAILABLE:
                print("[!] Voice calls not available - PyAudio not installed")
                self.show_prompt()
            elif hasattr(self, 'pending_call'):
                self.answer_call()
            else:
                print("[!] No incoming call")
                self.show_prompt()
        
        elif command == "/decline":
            if hasattr(self, 'pending_call'):
                self.decline_call()
            else:
                print("[!] No incoming call")
                self.show_prompt()
        
        elif command == "/mute":
            if not VOICE_AVAILABLE:
                print("[!] Voice calls not available")
                self.show_prompt()
            elif self.active_call:
                is_muted = self.active_call.toggle_mute()
                status = "MUTED" if is_muted else "UNMUTED"
                print(f"[*] Microphone {status}")
                self.show_prompt()
            else:
                print("[!] Not in a call")
                self.show_prompt()
        
        elif command == "/endcall":
            if self.active_call:
                self.end_call()
            else:
                print("[!] Not in a call")
                self.show_prompt()
        
        else:
            print("[!] Unknown command")
            print("[*] Use /help")
            self.show_prompt()
        
        return True
    
    def start_call(self, target: str):
        """Initiate a voice call"""
        if target == self.username:
            print("[!] Cannot call yourself")
            self.show_prompt()
            return
        
        if self.active_call:
            print("[!] Already in a call")
            self.show_prompt()
            return
        
        self.send_message({
            'type': 'call_request',
            'target': target,
            'voice_port': self.voice_port
        })
        
        print(f"[*] Calling {target}...")
        self.show_prompt()
    
    def answer_call(self):
        """Answer incoming call"""
        if not hasattr(self, 'pending_call'):
            return
        
        call_info = self.pending_call
        from_user = call_info['from']
        peer_ip = call_info['peer_ip']
        peer_port = call_info['peer_port']
        
        # Start voice call
        self.call_peer = from_user
        
        try:
            self.active_call = VoiceCall(peer_ip, peer_port, self.voice_port)
            
            if self.active_call.start():
                self.send_message({
                    'type': 'call_accept',
                    'target': from_user,
                    'voice_port': self.voice_port
                })
                
                print(f"[📞] Call connected with {from_user}")
                print(f"[*] Type '/mute' to toggle microphone, '/endcall' to hang up")
                delattr(self, 'pending_call')
                self.show_prompt()
            else:
                print("[!] Failed to start voice call")
                self.active_call = None
                self.call_peer = None
                delattr(self, 'pending_call')
                self.show_prompt()
        except Exception as e:
            print(f"[!] Voice call error: {e}")
            self.active_call = None
            self.call_peer = None
            delattr(self, 'pending_call')
            self.show_prompt()
    
    def decline_call(self):
        """Decline incoming call"""
        if not hasattr(self, 'pending_call'):
            return
        
        from_user = self.pending_call['from']
        
        self.send_message({
            'type': 'call_reject',
            'target': from_user
        })
        
        print(f"[*] Declined call from {from_user}")
        delattr(self, 'pending_call')
        self.show_prompt()
    
    def end_call(self):
        """End active voice call"""
        if not self.active_call:
            return
        
        self.active_call.stop()
        
        if self.call_peer:
            self.send_message({
                'type': 'call_end',
                'target': self.call_peer
            })
            
            print(f"\n[📞] Call with {self.call_peer} ended")
        
        self.active_call = None
        self.call_peer = None
        self.show_prompt()
    
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
        
        # End any active call
        if self.active_call:
            self.active_call.stop()
            self.active_call = None
            self.call_peer = None

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
    if VOICE_AVAILABLE:
        print("Voice Calls: ENABLED")
    else:
        print("Voice Calls: DISABLED (install pyaudio to enable)")
    print("="*60)

    host = input("Server address [localhost]: ").strip() or "localhost"
    port = int(input("Server port [9999]: ").strip() or "9999")

    username = input("Enter username: ").strip()

    client = SecureChatClient(host, port)
    if client.connect(username):
        client.run()

if __name__ == "__main__":
    main()