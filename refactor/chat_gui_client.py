"""
DartChat - Secure Chat GUI Client with TLS Encryption and Voice Calls
Modern GUI interface using tkinter with complete command support
Enhanced with voice calling functionality

LLM Usage: Chatgpt/Claude to fix errors and add comments
Authors: Ibrahim and Keith
"""

import os
# Force VM-safe rendering
os.environ["GDK_RENDERING"] = "false"
os.environ["LIBGL_ALWAYS_INDIRECT"] = "1"
os.environ["QT_X11_NO_MITSHM"] = "1"
os.environ["TK_USE_INPUT_METHODS"] = "0"
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import socket
import ssl
import json
import threading
import os
import base64
import sys
from typing import Optional
from datetime import datetime
import pyaudio
import struct
import time

class VoiceCall:
    """Manages a single voice call session"""
    
    def __init__(self, peer_ip: str, peer_port: int, local_port: int):
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


class SecureChatGUI:
    """Modern GUI for secure chat client with voice calls"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("DartChat - Secure Messaging")
        
        # Get screen dimensions
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        window_width = min(int(screen_width * 0.75), 1200)
        window_height = min(int(screen_height * 0.70), screen_height - 100)
        
        position_x = 10
        position_y = 10
        
        self.root.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")
        self.root.minsize(700, 450)
        
        # Connection variables
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
        self.voice_port = 5000  # Base port for voice
        
        # Create downloads directory
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
        
        # Enhanced color scheme
        self.bg_dark = "#0a0e1a"
        self.bg_medium = "#1a1f2e"
        self.bg_light = "#252a3d"
        self.accent = "#00ff88"
        self.accent_hover = "#00cc6e"
        self.text_color = "#e0e0e0"
        self.text_dim = "#888888"
        self.msg_bg = "#2a2f42"
        self.error_color = "#ff4444"
        self.call_color = "#4CAF50"
        
        # Setup GUI
        self.setup_connection_dialog()
        
    def setup_connection_dialog(self):
        """Initial connection dialog"""
        self.conn_frame = tk.Frame(self.root, bg=self.bg_dark)
        self.conn_frame.pack(fill=tk.BOTH, expand=True)
        
        center = tk.Frame(self.conn_frame, bg=self.bg_dark)
        center.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        title = tk.Label(center, text="DARTCHAT", 
                        font=("Arial Black", 32, "bold"), 
                        fg=self.accent, bg=self.bg_dark)
        title.pack(pady=(0, 5))
        
        subtitle = tk.Label(center, text="Secure Encrypted Messaging", 
                           font=("Arial", 12), 
                           fg=self.text_dim, bg=self.bg_dark)
        subtitle.pack(pady=(0, 30))
        
        fields_frame = tk.Frame(center, bg=self.bg_dark)
        fields_frame.pack(pady=10)
        
        tk.Label(fields_frame, text="Server Address:", fg=self.text_color, 
                bg=self.bg_dark, font=("Arial", 11)).grid(row=0, column=0, sticky='w', pady=8)
        self.host_entry = tk.Entry(fields_frame, width=35, font=("Arial", 11),
                                   bg=self.bg_light, fg=self.text_color,
                                   insertbackground=self.text_color, relief=tk.FLAT)
        self.host_entry.insert(0, "localhost")
        self.host_entry.grid(row=0, column=1, pady=8, padx=10)
        
        tk.Label(fields_frame, text="Port:", fg=self.text_color, 
                bg=self.bg_dark, font=("Arial", 11)).grid(row=1, column=0, sticky='w', pady=8)
        self.port_entry = tk.Entry(fields_frame, width=35, font=("Arial", 11),
                                   bg=self.bg_light, fg=self.text_color,
                                   insertbackground=self.text_color, relief=tk.FLAT)
        self.port_entry.insert(0, "9999")
        self.port_entry.grid(row=1, column=1, pady=8, padx=10)
        
        tk.Label(fields_frame, text="Username:", fg=self.text_color, 
                bg=self.bg_dark, font=("Arial", 11)).grid(row=2, column=0, sticky='w', pady=8)
        self.username_entry = tk.Entry(fields_frame, width=35, font=("Arial", 11),
                                       bg=self.bg_light, fg=self.text_color,
                                       insertbackground=self.text_color, relief=tk.FLAT)
        self.username_entry.grid(row=2, column=1, pady=8, padx=10)
        self.username_entry.bind('<Return>', lambda e: self.connect_to_server())
        self.username_entry.focus()
        
        self.connect_btn = tk.Button(center, text="Connect to DartChat", 
                                     command=self.connect_to_server,
                                     bg=self.accent, fg=self.bg_dark,
                                     font=("Arial", 13, "bold"),
                                     padx=40, pady=12, cursor="hand2",
                                     relief=tk.FLAT, borderwidth=0)
        self.connect_btn.pack(pady=25)
        self.connect_btn.bind('<Enter>', lambda e: self.connect_btn.config(bg=self.accent_hover))
        self.connect_btn.bind('<Leave>', lambda e: self.connect_btn.config(bg=self.accent))
        
        self.conn_status = tk.Label(center, text="", fg=self.error_color, 
                                    bg=self.bg_dark, font=("Arial", 10))
        self.conn_status.pack()
        
    def setup_main_gui(self):
        """Setup main chat interface"""
        self.conn_frame.destroy()
        
        main = tk.Frame(self.root, bg=self.bg_dark)
        main.pack(fill=tk.BOTH, expand=True)
        
        # Top bar
        top_bar = tk.Frame(main, bg=self.bg_medium, height=60)
        top_bar.pack(fill=tk.X, side=tk.TOP)
        top_bar.pack_propagate(False)
        
        left_frame = tk.Frame(top_bar, bg=self.bg_medium)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        tk.Label(left_frame, text="DARTCHAT", 
                fg=self.accent, bg=self.bg_medium,
                font=("Arial Black", 16, "bold")).pack(side=tk.LEFT, padx=15, pady=15)
        
        tk.Label(left_frame, text="|", 
                fg=self.text_dim, bg=self.bg_medium,
                font=("Arial", 16)).pack(side=tk.LEFT, padx=5)
        
        tk.Label(left_frame, text=f" {self.username}", 
                fg=self.text_color, bg=self.bg_medium,
                font=("Arial", 11, "bold")).pack(side=tk.LEFT, padx=10)
        
        self.room_label = tk.Label(left_frame, text=f"# {self.current_room}",
                                   fg=self.accent, bg=self.bg_medium,
                                   font=("Arial", 11))
        self.room_label.pack(side=tk.LEFT, padx=5)
        
        # Call status indicator with end call button
        self.call_frame = tk.Frame(left_frame, bg=self.bg_medium)
        self.call_frame.pack(side=tk.LEFT, padx=10)
        
        self.call_status_label = tk.Label(self.call_frame, text="",
                                         fg=self.call_color, bg=self.bg_medium,
                                         font=("Arial", 10, "bold"))
        self.call_status_label.pack(side=tk.LEFT)
        
        self.end_call_btn = tk.Button(self.call_frame, text="✗ End", 
                                      command=self.end_call,
                                      bg=self.error_color, fg="white",
                                      font=("Arial", 9, "bold"),
                                      padx=8, pady=4, cursor="hand2",
                                      relief=tk.FLAT, borderwidth=0)
        # Hidden by default
        self.mute_btn = tk.Button(self.call_frame, text="🔇 Mute", 
                                  command=self.toggle_mute_from_bar,
                                  bg=self.bg_light, fg=self.text_color,
                                  font=("Arial", 9, "bold"),
                                  padx=8, pady=4, cursor="hand2",
                                  relief=tk.FLAT, borderwidth=0)
        
        btn_frame = tk.Frame(top_bar, bg=self.bg_medium)
        btn_frame.pack(side=tk.RIGHT, padx=10)
        
        for text, cmd in [("Help", self.show_help),
                          ("Received", self.show_received_files),
                          ("Send File", self.send_file_dialog),
                          ("Call", self.show_call_dialog),
                          ("Users", self.show_users),
                          ("Rooms", self.show_rooms)]:
            btn = tk.Button(btn_frame, text=text, command=cmd,
                           bg=self.bg_light, fg=self.text_color, 
                           font=("Arial", 10, "bold"),
                           padx=12, pady=8, cursor="hand2",
                           relief=tk.FLAT, borderwidth=0)
            btn.pack(side=tk.RIGHT, padx=3)
            btn.bind('<Enter>', lambda e, b=btn: b.config(bg=self.accent, fg=self.bg_dark))
            btn.bind('<Leave>', lambda e, b=btn: b.config(bg=self.bg_light, fg=self.text_color))
        
        # Content area
        content = tk.Frame(main, bg=self.bg_dark)
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))
        
        chat_frame = tk.Frame(content, bg=self.bg_dark)
        chat_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        
        scrollbar = tk.Scrollbar(chat_frame, bg=self.bg_medium, troughcolor=self.bg_dark,
                                activebackground=self.accent, width=14)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.chat_area = tk.Text(
            chat_frame,
            wrap=tk.WORD,
            bg=self.bg_light,
            fg=self.text_color,
            font=("Consolas", 9),
            yscrollcommand=scrollbar.set,
            state=tk.DISABLED,
            relief=tk.FLAT,
            padx=12,
            pady=12,
            height=15
        )
        self.chat_area.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.config(command=self.chat_area.yview)
        
        # Input area
        input_frame = tk.Frame(content, bg=self.bg_dark, height=50)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(8, 0))
        input_frame.pack_propagate(False)
        
        entry_container = tk.Frame(input_frame, bg=self.msg_bg, highlightthickness=2,
                                  highlightbackground=self.accent, height=40)
        entry_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        entry_container.pack_propagate(False)
        
        self.message_entry = tk.Entry(
            entry_container,
            bg=self.msg_bg,
            fg=self.text_color,
            font=("Arial", 11, "bold"),
            relief=tk.FLAT,
            insertbackground=self.accent,
            borderwidth=0
        )
        self.message_entry.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        self.message_entry.bind("<Return>", lambda e: self.send_message())
        
        self.root.after(200, lambda: self.message_entry.focus_force())
        
        btn_container = tk.Frame(input_frame, bg=self.bg_dark)
        btn_container.pack(side=tk.LEFT)
        
        pm_btn = tk.Button(btn_container, text="PM", command=self.send_pm_dialog,
                          bg=self.bg_light, fg=self.text_color, 
                          font=("Arial", 10, "bold"),
                          padx=14, pady=10, cursor="hand2",
                          relief=tk.FLAT, borderwidth=2)
        pm_btn.pack(side=tk.LEFT, padx=(0, 4))
        pm_btn.bind('<Enter>', lambda e: pm_btn.config(bg=self.accent, fg=self.bg_dark))
        pm_btn.bind('<Leave>', lambda e: pm_btn.config(bg=self.bg_light, fg=self.text_color))
        
        send_btn = tk.Button(btn_container, text="SEND", command=self.send_message,
                            bg=self.accent, fg=self.bg_dark, 
                            font=("Arial", 10, "bold"),
                            padx=18, pady=10, cursor="hand2",
                            relief=tk.FLAT, borderwidth=2)
        send_btn.pack(side=tk.LEFT)
        send_btn.bind('<Enter>', lambda e: send_btn.config(bg=self.accent_hover))
        send_btn.bind('<Leave>', lambda e: send_btn.config(bg=self.accent))
        
        # Welcome messages
        self.display_message("System", "=" * 60, "system")
        self.display_message("System", "Welcome to DartChat - Secure Encrypted Messaging", "system")
        self.display_message("System", "=" * 60, "system")
        self.display_message("System", f"[+] Connected as '{self.username}' in room '#{self.current_room}'", "system")
        self.display_message("System", "Click 'Help' button to see all available commands", "system")
        self.display_message("System", "Click 'Call' button to start a voice call with someone", "system")
        self.display_message("System", "=" * 60, "system")
        
    def connect_to_server(self):
        """Connect to chat server"""
        host = self.host_entry.get().strip() or "localhost"
        port = int(self.port_entry.get().strip() or "9999")
        username = self.username_entry.get().strip()
        
        if not username:
            self.conn_status.config(text="Please enter a username")
            return
        
        self.conn_status.config(text="Connecting...", fg="#ffd93d")
        self.connect_btn.config(state=tk.DISABLED)
        
        def connect_thread():
            try:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                context.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM")
                
                raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket = context.wrap_socket(raw, server_hostname=host)
                self.socket.connect((host, port))
                
                auth_req = self.receive_message()
                if not auth_req or auth_req.get("type") != "auth_request":
                    raise Exception("Invalid server handshake")
                
                self.send_message_raw({"type": "auth", "username": username})
                
                self.running = True
                threading.Thread(target=self.receive_handler, daemon=True).start()
                
                import time
                for _ in range(20):
                    if self.connected:
                        self.root.after(0, self.setup_main_gui)
                        return
                    time.sleep(0.1)
                
                raise Exception("Authentication timeout")
                
            except Exception as e:
                self.root.after(0, lambda: self.conn_status.config(
                    text=f"Connection failed: {str(e)}", fg=self.error_color))
                self.root.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
        
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def send_message_raw(self, message: dict):
        """Send JSON message to server"""
        try:
            data = json.dumps(message).encode('utf-8')
            self.socket.sendall(len(data).to_bytes(4, byteorder='big') + data)
        except:
            self.disconnect()
    
    def receive_message(self):
        """Receive JSON message from server"""
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
        """Handle incoming messages"""
        while self.running:
            msg = self.receive_message()
            if not msg:
                break
            self.root.after(0, self.process_message, msg)
        
        if self.running:
            self.root.after(0, lambda: messagebox.showerror(
                "Disconnected", "Lost connection to server"))
            self.root.after(0, self.disconnect)
    
    def process_message(self, msg: dict):
        """Process received messages"""
        msg_type = msg.get('type')
        
        if msg_type == 'auth_success':
            self.username = msg["username"]
            self.current_room = msg["room"]
            self.connected = True
        
        elif msg_type == 'message':
            if hasattr(self, 'chat_area'):
                self.display_message(msg['username'], msg['content'], "message", msg['timestamp'])
        
        elif msg_type == 'system':
            if hasattr(self, 'chat_area'):
                self.display_message("System", msg['message'], "system")
        
        elif msg_type == 'room_changed':
            self.current_room = msg.get('room')
            if hasattr(self, 'room_label'):
                self.room_label.config(text=f"# {self.current_room}")
            if hasattr(self, 'chat_area'):
                self.display_message("System", msg.get('message'), "system")
        
        elif msg_type == 'private_message':
            if hasattr(self, 'chat_area'):
                self.display_message(f"PM from {msg['from']}", msg['content'], "pm", msg['timestamp'])
        
        elif msg_type == 'private_sent':
            if hasattr(self, 'chat_area'):
                self.display_message("System", f"PM sent to {msg['to']}", "system")
        
        elif msg_type == 'room_list':
            rooms = msg.get('rooms', [])
            if hasattr(self, 'chat_area'):
                self.display_message("System", f"Available rooms: {', '.join(rooms)}", "system")
        
        elif msg_type == 'user_list':
            users = msg.get('users', [])
            if hasattr(self, 'chat_area'):
                self.display_message("System", f"Users in #{msg['room']}: {', '.join(users)}", "system")
        
        elif msg_type == 'file_offer':
            self.handle_file_offer(msg)
        
        elif msg_type == 'file_transfer':
            self.handle_file_transfer(msg)
        
        elif msg_type == 'file_rejected':
            if hasattr(self, 'chat_area'):
                self.display_message("System", f"{msg['target']} rejected your file: {msg['filename']}", "system")
        
        elif msg_type == 'call_request':
            self.handle_call_request(msg)
        
        elif msg_type == 'call_accepted':
            self.handle_call_accepted(msg)
        
        elif msg_type == 'call_rejected':
            if hasattr(self, 'chat_area'):
                self.display_message("System", f"{msg['from']} rejected your call", "system")
        
        elif msg_type == 'call_ended':
            self.handle_call_ended(msg)
        
        elif msg_type == 'error':
            if hasattr(self, 'chat_area'):
                self.display_message("System", f"Error: {msg.get('message', 'Unknown error')}", "system")
    
    def display_message(self, sender: str, content: str, msg_type: str, timestamp: str = None):
        """Display message in chat area"""
        self.chat_area.config(state=tk.NORMAL)
        
        if not timestamp:
            timestamp = datetime.now().strftime("%H:%M:%S")
        
        if msg_type == "system":
            self.chat_area.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.chat_area.insert(tk.END, f"{content}\n", "system")
        elif msg_type == "pm":
            self.chat_area.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.chat_area.insert(tk.END, f"{sender}: ", "pm_sender")
            self.chat_area.insert(tk.END, f"{content}\n", "pm")
        else:
            self.chat_area.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.chat_area.insert(tk.END, f"{sender}: ", "username")
            self.chat_area.insert(tk.END, f"{content}\n")
        
        self.chat_area.tag_config("timestamp", foreground=self.text_dim, font=("Consolas", 9))
        self.chat_area.tag_config("system", foreground="#ffd93d", font=("Consolas", 10, "bold"))
        self.chat_area.tag_config("username", foreground=self.accent, font=("Consolas", 10, "bold"))
        self.chat_area.tag_config("pm_sender", foreground="#ff6b9d", font=("Consolas", 10, "bold"))
        self.chat_area.tag_config("pm", foreground="#ffb3d9")
        
        self.chat_area.config(state=tk.DISABLED)
        self.chat_area.see(tk.END)
    
    def send_message(self):
        """Send chat message"""
        text = self.message_entry.get().strip()
        if not text:
            return
        
        self.send_message_raw({'type': 'message', 'content': text})
        self.message_entry.delete(0, tk.END)
    
    def show_call_dialog(self):
        """Show voice call dialog"""
        if self.active_call:
            # Already in a call, show call controls
            self.show_call_controls()
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Voice Call - DartChat")
        dialog.geometry("500x300")
        dialog.configure(bg=self.bg_dark)
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Start Voice Call", font=("Arial", 16, "bold"),
                fg=self.accent, bg=self.bg_dark).pack(pady=15)
        
        tk.Label(dialog, text="Call user (username):", 
                fg=self.text_color, bg=self.bg_dark, font=("Arial", 11)).pack(pady=(10, 5))
        
        target_var = tk.StringVar()
        target_entry = tk.Entry(dialog, textvariable=target_var, width=35,
                               font=("Arial", 11), bg=self.bg_light, 
                               fg=self.text_color, relief=tk.FLAT)
        target_entry.pack(pady=5, ipady=5)
        target_entry.focus()
        
        tk.Label(dialog, text="User must be in the same room", 
                fg=self.text_dim, bg=self.bg_dark, font=("Arial", 9)).pack(pady=10)
        
        def initiate_call():
            target = target_var.get().strip()
            
            if not target:
                messagebox.showwarning("No Recipient", "Please enter a username")
                return
            
            if target == self.username:
                messagebox.showwarning("Invalid", "Cannot call yourself")
                return
            
            # Send call request
            self.send_message_raw({
                'type': 'call_request',
                'target': target,
                'voice_port': self.voice_port
            })
            
            self.display_message("System", f"Calling {target}...", "system")
            dialog.destroy()
        
        tk.Button(dialog, text="Call", command=initiate_call,
                 bg=self.call_color, fg="white", font=("Arial", 12, "bold"),
                 padx=30, pady=10, cursor="hand2", relief=tk.FLAT).pack(pady=15)
    
    def handle_call_request(self, msg: dict):
        """Handle incoming call request"""
        from_user = msg['from']
        peer_ip = msg['peer_ip']
        peer_port = msg['peer_port']
        
        self.display_message("System", f"📞 Incoming call from {from_user}...", "system")
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Incoming Call - DartChat")
        dialog.geometry("500x300")
        dialog.configure(bg=self.bg_dark)
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="📞 Incoming Voice Call", 
                font=("Arial", 16, "bold"),
                fg=self.call_color, bg=self.bg_dark).pack(pady=20)
        
        info_frame = tk.Frame(dialog, bg=self.bg_medium, relief=tk.FLAT)
        info_frame.pack(pady=10, padx=40, fill=tk.X)
        
        tk.Label(info_frame, text=f"From: {from_user}", 
                fg=self.text_color, bg=self.bg_medium, 
                font=("Arial", 14, "bold")).pack(pady=15, padx=20)
        
        tk.Label(dialog, text="Do you want to answer?", 
                fg=self.text_color, bg=self.bg_dark, 
                font=("Arial", 11)).pack(pady=15)
        
        def accept():
            # Start voice call
            self.call_peer = from_user
            self.active_call = VoiceCall(peer_ip, peer_port, self.voice_port)
            
            if self.active_call.start():
                self.send_message_raw({
                    'type': 'call_accept',
                    'target': from_user,
                    'voice_port': self.voice_port
                })
                
                self.display_message("System", f"📞 Call connected with {from_user}", "system")
                self.update_call_status(f"🔊 In call with {from_user}")
                dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to start voice call")
                self.active_call = None
                self.call_peer = None
                dialog.destroy()
        
        def reject():
            self.send_message_raw({
                'type': 'call_reject',
                'target': from_user
            })
            self.display_message("System", f"Rejected call from {from_user}", "system")
            dialog.destroy()
        
        btn_frame = tk.Frame(dialog, bg=self.bg_dark)
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="✓ Answer", command=accept,
                 bg=self.call_color, fg="white", 
                 font=("Arial", 12, "bold"),
                 padx=30, pady=12, cursor="hand2", relief=tk.FLAT).pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="✗ Decline", command=reject,
                 bg=self.error_color, fg="white", 
                 font=("Arial", 12, "bold"),
                 padx=30, pady=12, cursor="hand2", relief=tk.FLAT).pack(side=tk.LEFT, padx=10)
    
    def handle_call_accepted(self, msg: dict):
        """Handle call acceptance"""
        from_user = msg['from']
        peer_ip = msg['peer_ip']
        peer_port = msg['peer_port']
        
        # Start voice call
        self.call_peer = from_user
        self.active_call = VoiceCall(peer_ip, peer_port, self.voice_port)
        
        if self.active_call.start():
            self.display_message("System", f"📞 {from_user} answered - Call connected!", "system")
            self.update_call_status(f"🔊 In call with {from_user}")
        else:
            messagebox.showerror("Error", "Failed to start voice call")
            self.active_call = None
            self.call_peer = None
    
    def show_call_controls(self):
        """Show call control window"""
        if not self.active_call:
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Call Controls - DartChat")
        dialog.geometry("400x300")
        dialog.configure(bg=self.bg_dark)
        dialog.transient(self.root)
        
        tk.Label(dialog, text="🔊 Call Active", 
                font=("Arial", 16, "bold"),
                fg=self.call_color, bg=self.bg_dark).pack(pady=15)
        
        tk.Label(dialog, text=f"Connected with: {self.call_peer}", 
                fg=self.text_color, bg=self.bg_dark, 
                font=("Arial", 12, "bold")).pack(pady=10)
        
        mute_status = tk.Label(dialog, text="🎤 Microphone: ON", 
                              fg=self.text_color, bg=self.bg_dark, 
                              font=("Arial", 11))
        mute_status.pack(pady=15)
        
        def toggle_mute():
            if self.active_call:
                is_muted = self.active_call.toggle_mute()
                if is_muted:
                    mute_status.config(text="🔇 Microphone: MUTED", fg=self.error_color)
                else:
                    mute_status.config(text="🎤 Microphone: ON", fg=self.text_color)
        
        def end_call():
            self.end_call()
            dialog.destroy()
        
        btn_frame = tk.Frame(dialog, bg=self.bg_dark)
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="🔇 Mute/Unmute", command=toggle_mute,
                 bg=self.bg_light, fg=self.text_color, 
                 font=("Arial", 11, "bold"),
                 padx=20, pady=12, cursor="hand2", relief=tk.FLAT).pack(pady=10)
        
        tk.Button(btn_frame, text="📞 End Call", command=end_call,
                 bg=self.error_color, fg="white", 
                 font=("Arial", 12, "bold"),
                 padx=30, pady=12, cursor="hand2", relief=tk.FLAT).pack(pady=10)
    
    def end_call(self):
        """End active voice call"""
        if self.active_call:
            self.active_call.stop()
            
            if self.call_peer:
                self.send_message_raw({
                    'type': 'call_end',
                    'target': self.call_peer
                })
                
                self.display_message("System", f"📞 Call with {self.call_peer} ended", "system")
            
            self.active_call = None
            self.call_peer = None
            self.update_call_status("")
    
    def handle_call_ended(self, msg: dict):
        """Handle call ended by peer"""
        from_user = msg['from']
        
        if self.active_call and self.call_peer == from_user:
            self.active_call.stop()
            self.active_call = None
            self.call_peer = None
            self.update_call_status("")
            
            self.display_message("System", f"📞 {from_user} ended the call", "system")
    
    def toggle_mute_from_bar(self):
        """Toggle mute from top bar button"""
        if self.active_call:
            is_muted = self.active_call.toggle_mute()
            if is_muted:
                self.mute_btn.config(text="🎤 Unmute", bg=self.error_color, fg="white")
            else:
                self.mute_btn.config(text="🔇 Mute", bg=self.bg_light, fg=self.text_color)
    
    def update_call_status(self, status: str):
        """Update call status in UI"""
        if hasattr(self, 'call_status_label'):
            self.call_status_label.config(text=status)
            
            # Show/hide call control buttons
            if status and hasattr(self, 'end_call_btn'):
                self.mute_btn.pack(side=tk.LEFT, padx=2)
                self.end_call_btn.pack(side=tk.LEFT, padx=2)
            elif hasattr(self, 'end_call_btn'):
                self.mute_btn.pack_forget()
                self.end_call_btn.pack_forget()
                # Reset mute button state
                self.mute_btn.config(text="🔇 Mute", bg=self.bg_light, fg=self.text_color)
    
    def show_help(self):
        """Show help dialog with all commands"""
        dialog = tk.Toplevel(self.root)
        dialog.title("DartChat Commands")
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        dialog_width = min(700, int(screen_width * 0.6))
        dialog_height = min(600, int(screen_height * 0.7))
        
        pos_x = int((screen_width - dialog_width) / 2)
        pos_y = int((screen_height - dialog_height) / 2)
        
        dialog.geometry(f"{dialog_width}x{dialog_height}+{pos_x}+{pos_y}")
        dialog.configure(bg=self.bg_dark)
        dialog.transient(self.root)
        
        tk.Label(dialog, text="DartChat Commands & Features", 
                font=("Arial", 16, "bold"),
                fg=self.accent, bg=self.bg_dark).pack(pady=15)
        
        text_frame = tk.Frame(dialog, bg=self.bg_dark)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        scrollbar = tk.Scrollbar(text_frame, bg=self.bg_medium, activebackground=self.accent, width=14)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        help_text = tk.Text(text_frame, bg=self.bg_light, fg=self.text_color,
                           font=("Consolas", 10), wrap=tk.WORD,
                           yscrollcommand=scrollbar.set, relief=tk.FLAT,
                           padx=15, pady=15)
        help_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=help_text.yview)
        
        help_content = """
===============================================================

BASIC MESSAGING
===============================================================
* Type in the message box and press Enter or click Send
* Messages are sent to everyone in your current room

PRIVATE MESSAGING
===============================================================
* Click the PM button to send a private message
* Only the recipient will see your message

VOICE CALLS
===============================================================
Starting a Call:
   * Click the Call button
   * Enter the username you want to call
   * User must be in the same room as you
   * Wait for them to answer

Receiving a Call:
   * You'll get a popup when someone calls you
   * Click Answer to accept or Decline to reject
   * Only one call at a time is supported

During a Call:
   * Click Call button again to see controls
   * Use Mute/Unmute to toggle your microphone
   * Click End Call to hang up
   * Calls use UDP for real-time audio streaming

ROOM MANAGEMENT
===============================================================
* Click Rooms to see all available rooms
* Create a new room by typing a name and clicking Create
* Join an existing room by typing its name and clicking Join
* Voice calls only work within the same room

USER MANAGEMENT
===============================================================
* Click Users to see who's in your current room
* View all online users across all rooms

FILE TRANSFER
===============================================================
Send File to Specific User(s):
   * Click File button
   * Select a file
   * Enter username (or multiple: user1,user2,user3)
   * Click Send File

Broadcast File to Entire Room:
   * Click File button
   * Select a file
   * Leave recipient field empty
   * Click Send File
   * Everyone in the room will receive an offer

Receiving Files:
   * You'll get a popup when someone sends you a file
   * Click Yes to accept or No to reject
   * Accepted files are saved to 'downloads' folder
   * Click Files to see all received files

VIEWING RECEIVED FILES
===============================================================
* Click Files button to see all received files
* Select a file and click "Open Selected File"
* Click "Open Downloads Folder" to browse all files

FILE LIMITS
===============================================================
* Maximum file size: 10 MB
* All file types supported
* Files are encrypted during transfer

TIPS & TRICKS
===============================================================
[+] Press Enter to quickly send messages
[+] Voice calls use UDP - ensure ports are accessible
[+] You can send files to multiple users at once
[+] Private messages are completely private
[+] Create themed rooms for different topics
[+] All communication is encrypted with TLS

===============================================================
"""
        
        help_text.insert("1.0", help_content)
        help_text.config(state=tk.DISABLED)
        
        tk.Button(dialog, text="Close", command=dialog.destroy,
                 bg=self.accent, fg=self.bg_dark, font=("Arial", 11, "bold"),
                 padx=30, pady=10, cursor="hand2", relief=tk.FLAT).pack(pady=15)
    
    def send_pm_dialog(self):
        """Show private message dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Send Private Message - DartChat")
        dialog.geometry("500x300")
        dialog.configure(bg=self.bg_dark)
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Send Private Message", font=("Arial", 16, "bold"),
                fg=self.accent, bg=self.bg_dark).pack(pady=15)
        
        tk.Label(dialog, text="Send to (username):", 
                fg=self.text_color, bg=self.bg_dark, font=("Arial", 11)).pack(pady=(10, 5))
        
        target_var = tk.StringVar()
        target_entry = tk.Entry(dialog, textvariable=target_var, width=35,
                               font=("Arial", 11), bg=self.bg_light, 
                               fg=self.text_color, relief=tk.FLAT)
        target_entry.pack(pady=5, ipady=5)
        target_entry.focus()
        
        tk.Label(dialog, text="Message:", 
                fg=self.text_color, bg=self.bg_dark, font=("Arial", 11)).pack(pady=(15, 5))
        
        msg_text = tk.Text(dialog, width=40, height=6, font=("Arial", 11),
                          bg=self.bg_light, fg=self.text_color, relief=tk.FLAT)
        msg_text.pack(pady=5, padx=30)
        
        def send():
            target = target_var.get().strip()
            message = msg_text.get("1.0", tk.END).strip()
            
            if not target:
                messagebox.showwarning("No Recipient", "Please enter a username")
                return
            
            if not message:
                messagebox.showwarning("No Message", "Please enter a message")
                return
            
            self.send_message_raw({
                'type': 'private_message',
                'target': target,
                'content': message
            })
            dialog.destroy()
        
        tk.Button(dialog, text="Send PM", command=send,
                 bg=self.accent, fg=self.bg_dark, font=("Arial", 12, "bold"),
                 padx=30, pady=10, cursor="hand2", relief=tk.FLAT).pack(pady=15)
    
    def send_file_dialog(self):
        """Show file send dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Send File - DartChat")
        dialog.geometry("550x350")
        dialog.configure(bg=self.bg_dark)
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Send File", font=("Arial", 16, "bold"),
                fg=self.accent, bg=self.bg_dark).pack(pady=15)
        
        file_path = tk.StringVar()
        
        def browse():
            path = filedialog.askopenfilename(title="Select file to send")
            if path:
                file_path.set(path)
        
        tk.Label(dialog, text="Select File:", 
                fg=self.text_color, bg=self.bg_dark, font=("Arial", 11)).pack(pady=(10, 5))
        
        file_frame = tk.Frame(dialog, bg=self.bg_dark)
        file_frame.pack(pady=10, padx=30, fill=tk.X)
        
        tk.Entry(file_frame, textvariable=file_path, width=35,
                font=("Arial", 10), bg=self.bg_light, fg=self.text_color,
                relief=tk.FLAT).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        tk.Button(file_frame, text="Browse", command=browse,
                 bg=self.accent, fg=self.bg_dark, font=("Arial", 10, "bold"),
                 cursor="hand2", relief=tk.FLAT, padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Label(dialog, text="Send to:", 
                fg=self.text_color, bg=self.bg_dark, font=("Arial", 11)).pack(pady=(15, 5))
        
        target_var = tk.StringVar()
        target_entry = tk.Entry(dialog, textvariable=target_var, width=40,
                               font=("Arial", 11), bg=self.bg_light, 
                               fg=self.text_color, relief=tk.FLAT)
        target_entry.pack(pady=5, ipady=5)
        
        info_frame = tk.Frame(dialog, bg=self.bg_dark)
        info_frame.pack(pady=5)
        
        tk.Label(info_frame, text="Single user: username", 
                fg=self.text_dim, bg=self.bg_dark, font=("Arial", 9)).pack()
        tk.Label(info_frame, text="Multiple users: user1,user2,user3", 
                fg=self.text_dim, bg=self.bg_dark, font=("Arial", 9)).pack()
        tk.Label(info_frame, text="Broadcast to room: leave empty", 
                fg=self.text_dim, bg=self.bg_dark, font=("Arial", 9)).pack()
        
        def send():
            path = file_path.get()
            target = target_var.get().strip()
            
            if not path:
                messagebox.showwarning("No File", "Please select a file to send")
                return
            
            self.send_file(path, target)
            dialog.destroy()
        
        tk.Button(dialog, text="Send File", command=send,
                 bg=self.accent, fg=self.bg_dark, font=("Arial", 12, "bold"),
                 padx=30, pady=10, cursor="hand2", relief=tk.FLAT).pack(pady=15)
    
    def send_file(self, filepath: str, target: str = ""):
        """Send file to user(s) or broadcast"""
        try:
            if not os.path.exists(filepath):
                messagebox.showerror("Error", "File not found")
                return
            
            filesize = os.path.getsize(filepath)
            if filesize > 10 * 1024 * 1024:
                messagebox.showerror("Error", "File too large (max 10MB)")
                return
            
            filename = os.path.basename(filepath)
            
            with open(filepath, 'rb') as f:
                filedata = f.read()
            
            encoded_data = base64.b64encode(filedata).decode('utf-8')
            
            if not target:
                self.send_message_raw({
                    'type': 'file_broadcast',
                    'filename': filename,
                    'filesize': filesize,
                    'data': encoded_data
                })
                self.display_message("System", f"Broadcasting {filename} to #{self.current_room}...", "system")
            else:
                targets = [t.strip() for t in target.split(',')]
                
                if self.username in targets:
                    messagebox.showwarning("Invalid Recipient", "Cannot send file to yourself")
                    return
                
                self.send_message_raw({
                    'type': 'file_send',
                    'targets': targets,
                    'filename': filename,
                    'filesize': filesize,
                    'data': encoded_data
                })
                
                if len(targets) == 1:
                    self.display_message("System", f"Sending {filename} to {target}...", "system")
                else:
                    self.display_message("System", f"Sending {filename} to {len(targets)} users...", "system")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send file: {str(e)}")
    
    def handle_file_offer(self, msg: dict):
        """Handle incoming file offer"""
        file_id = msg['file_id']
        self.pending_file_offers[file_id] = msg
        
        from_user = msg['from']
        filename = msg['filename']
        filesize = msg['filesize']
        is_broadcast = msg.get('broadcast', False)
        
        prefix = "Broadcast file" if is_broadcast else "File offer"
        size_kb = filesize / 1024
        
        if hasattr(self, 'chat_area'):
            self.display_message("System", 
                f"{prefix} from {from_user}: {filename} ({size_kb:.1f} KB)",
                "system")
        
        self.root.after(100, lambda: self.show_file_accept_dialog(file_id, from_user, filename, filesize))
    
    def show_file_accept_dialog(self, file_id: str, from_user: str, filename: str, filesize: int):
        """Show file accept/reject dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("File Transfer - DartChat")
        dialog.geometry("500x300")
        dialog.configure(bg=self.bg_dark)
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="Incoming File Transfer", 
                font=("Arial", 16, "bold"),
                fg=self.accent, bg=self.bg_dark).pack(pady=20)
        
        info_frame = tk.Frame(dialog, bg=self.bg_medium, relief=tk.FLAT)
        info_frame.pack(pady=10, padx=40, fill=tk.X)
        
        tk.Label(info_frame, text=f"From: {from_user}", 
                fg=self.text_color, bg=self.bg_medium, 
                font=("Arial", 12, "bold")).pack(pady=5, padx=20)
        
        tk.Label(info_frame, text=f"File: {filename}", 
                fg=self.text_color, bg=self.bg_medium, 
                font=("Arial", 11)).pack(pady=3, padx=20)
        
        size_kb = filesize / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
        tk.Label(info_frame, text=f"Size: {size_str}", 
                fg=self.text_color, bg=self.bg_medium, 
                font=("Arial", 11)).pack(pady=3, padx=20)
        
        tk.Label(info_frame, text=f"ID: {file_id}", 
                fg=self.text_dim, bg=self.bg_medium, 
                font=("Arial", 9)).pack(pady=(3, 10), padx=20)
        
        tk.Label(dialog, text="Do you want to accept this file?", 
                fg=self.text_color, bg=self.bg_dark, 
                font=("Arial", 11)).pack(pady=15)
        
        def accept():
            self.send_message_raw({'type': 'file_accept', 'file_id': file_id})
            if hasattr(self, 'chat_area'):
                self.display_message("System", f"Accepting {filename} from {from_user}...", "system")
            dialog.destroy()
        
        def reject():
            self.send_message_raw({'type': 'file_reject', 'file_id': file_id})
            if file_id in self.pending_file_offers:
                del self.pending_file_offers[file_id]
            if hasattr(self, 'chat_area'):
                self.display_message("System", f"Rejected {filename} from {from_user}", "system")
            dialog.destroy()
        
        btn_frame = tk.Frame(dialog, bg=self.bg_dark)
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="[+] Accept", command=accept,
                 bg=self.accent, fg=self.bg_dark, 
                 font=("Arial", 12, "bold"),
                 padx=30, pady=12, cursor="hand2", relief=tk.FLAT).pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="[-] Reject", command=reject,
                 bg=self.error_color, fg="white", 
                 font=("Arial", 12, "bold"),
                 padx=30, pady=12, cursor="hand2", relief=tk.FLAT).pack(side=tk.LEFT, padx=10)
    
    def handle_file_transfer(self, msg: dict):
        """Handle incoming file data"""
        try:
            filename = msg['filename']
            filedata = msg['data']
            from_user = msg['from']
            
            file_bytes = base64.b64decode(filedata)
            filepath = os.path.join(self.download_dir, filename)
            
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(filepath):
                filepath = os.path.join(self.download_dir, f"{base}_{counter}{ext}")
                counter += 1
            
            with open(filepath, 'wb') as f:
                f.write(file_bytes)
            
            file_info = {
                'filename': os.path.basename(filepath),
                'filepath': filepath,
                'from': from_user,
                'size': len(file_bytes),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.received_files.append(file_info)
            
            if hasattr(self, 'chat_area'):
                self.display_message("System", 
                    f"File received from {from_user}: {filename}", 
                    "system")
        
        except Exception as e:
            if hasattr(self, 'chat_area'):
                self.display_message("System", f"Error receiving file: {str(e)}", "system")
    
    def show_rooms(self):
        """Show available rooms"""
        self.send_message_raw({'type': 'list_rooms'})
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Rooms - DartChat")
        dialog.geometry("500x500")
        dialog.configure(bg=self.bg_dark)
        dialog.transient(self.root)
        
        tk.Label(dialog, text="Chat Rooms", font=("Arial", 16, "bold"),
                fg=self.accent, bg=self.bg_dark).pack(pady=15)
        
        tk.Label(dialog, text=f"Current room: #{self.current_room}",
                fg=self.text_color, bg=self.bg_dark, font=("Arial", 11, "bold")).pack(pady=5)
        
        create_section = tk.Frame(dialog, bg=self.bg_medium, relief=tk.FLAT)
        create_section.pack(pady=15, padx=30, fill=tk.X)
        
        tk.Label(create_section, text="Create New Room", fg=self.accent,
                bg=self.bg_medium, font=("Arial", 12, "bold")).pack(pady=(10, 5))
        
        create_frame = tk.Frame(create_section, bg=self.bg_medium)
        create_frame.pack(pady=10, padx=20, fill=tk.X)
        
        room_name = tk.Entry(create_frame, font=("Arial", 11),
                            bg=self.bg_light, fg=self.text_color, relief=tk.FLAT)
        room_name.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 5))
        
        def create():
            name = room_name.get().strip()
            if name:
                self.send_message_raw({'type': 'create_room', 'room_name': name})
                room_name.delete(0, tk.END)
                self.display_message("System", f"Creating room '{name}'...", "system")
        
        tk.Button(create_frame, text="Create", command=create,
                 bg=self.accent, fg=self.bg_dark, font=("Arial", 10, "bold"),
                 cursor="hand2", relief=tk.FLAT, padx=15, pady=5).pack(side=tk.LEFT)
        
        tk.Label(create_section, text="", bg=self.bg_medium).pack(pady=5)
        
        join_section = tk.Frame(dialog, bg=self.bg_medium, relief=tk.FLAT)
        join_section.pack(pady=15, padx=30, fill=tk.X)
        
        tk.Label(join_section, text="Join Existing Room", fg=self.accent,
                bg=self.bg_medium, font=("Arial", 12, "bold")).pack(pady=(10, 5))
        
        tk.Label(join_section, text="Enter room name:", fg=self.text_color,
                bg=self.bg_medium, font=("Arial", 10)).pack(pady=5)
        
        join_entry = tk.Entry(join_section, font=("Arial", 11), width=30,
                             bg=self.bg_light, fg=self.text_color, relief=tk.FLAT)
        join_entry.pack(pady=10, ipady=5)
        
        def join():
            name = join_entry.get().strip()
            if name:
                self.send_message_raw({'type': 'join_room', 'room_name': name})
                dialog.destroy()
        
        tk.Button(join_section, text="Join Room", command=join,
                 bg=self.accent, fg=self.bg_dark, font=("Arial", 11, "bold"),
                 padx=25, pady=10, cursor="hand2", relief=tk.FLAT).pack(pady=10)
        
        tk.Label(join_section, text="", bg=self.bg_medium).pack(pady=5)
        
        tk.Button(dialog, text="Close", command=dialog.destroy,
                 bg=self.bg_light, fg=self.text_color, font=("Arial", 10),
                 padx=20, pady=8, cursor="hand2", relief=tk.FLAT).pack(pady=15)
    
    def show_users(self):
        """Show users in room"""
        self.send_message_raw({'type': 'list_users'})
        self.display_message("System", "Fetching user list...", "system")
    
    def show_received_files(self):
        """Show received files"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Received Files - DartChat")
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        dialog_width = min(800, int(screen_width * 0.7))
        dialog_height = min(550, int(screen_height * 0.7))
        
        pos_x = int((screen_width - dialog_width) / 2)
        pos_y = int((screen_height - dialog_height) / 2)
        
        dialog.geometry(f"{dialog_width}x{dialog_height}+{pos_x}+{pos_y}")
        dialog.configure(bg=self.bg_dark)
        dialog.transient(self.root)
        
        tk.Label(dialog, text="Received Files", font=("Arial", 16, "bold"),
                fg=self.accent, bg=self.bg_dark).pack(pady=15)
        
        if not self.received_files:
            empty_frame = tk.Frame(dialog, bg=self.bg_dark)
            empty_frame.pack(expand=True)
            
            tk.Label(empty_frame, text="[No Files]", 
                    fg=self.text_dim, bg=self.bg_dark, font=("Arial", 24)).pack(pady=20)
            tk.Label(empty_frame, text="No files received yet",
                    fg=self.text_color, bg=self.bg_dark, font=("Arial", 14, "bold")).pack()
            tk.Label(empty_frame, text="Files will appear here when someone sends you one",
                    fg=self.text_dim, bg=self.bg_dark, font=("Arial", 11)).pack(pady=10)
            
            tk.Button(dialog, text="Close", command=dialog.destroy,
                     bg=self.accent, fg=self.bg_dark, font=("Arial", 11, "bold"),
                     padx=25, pady=10, cursor="hand2", relief=tk.FLAT).pack(pady=20)
            return
        
        tk.Label(dialog, text=f"Total files: {len(self.received_files)}", 
                fg=self.text_dim, bg=self.bg_dark, font=("Arial", 10)).pack(pady=5)
        
        frame = tk.Frame(dialog, bg=self.bg_dark)
        frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=15)
        
        scrollbar = tk.Scrollbar(frame, bg=self.bg_medium, activebackground=self.accent, width=14)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(frame, bg=self.bg_light, fg=self.text_color,
                            font=("Consolas", 10), yscrollcommand=scrollbar.set,
                            relief=tk.FLAT, selectbackground=self.accent,
                            selectforeground=self.bg_dark, borderwidth=0,
                            activestyle='none')
        listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        for f in self.received_files:
            size = f['size'] / 1024
            unit = "KB"
            if size > 1024:
                size /= 1024
                unit = "MB"
            listbox.insert(tk.END, f"{f['filename']:<30} | from {f['from']:<15} | {size:>6.1f} {unit} | {f['timestamp']}")
        
        def open_file():
            selection = listbox.curselection()
            if selection:
                file_info = self.received_files[selection[0]]
                try:
                    if os.name == 'nt':
                        os.startfile(file_info['filepath'])
                    elif os.name == 'posix':
                        import subprocess
                        if sys.platform == 'darwin':
                            subprocess.call(['open', file_info['filepath']])
                        else:
                            subprocess.call(['xdg-open', file_info['filepath']])
                except Exception as e:
                    messagebox.showerror("Error", f"Could not open file: {str(e)}")
            else:
                messagebox.showinfo("No Selection", "Please select a file to open")
        
        def open_folder():
            try:
                if os.name == 'nt':
                    os.startfile(self.download_dir)
                elif os.name == 'posix':
                    import subprocess
                    if sys.platform == 'darwin':
                        subprocess.call(['open', self.download_dir])
                    else:
                        subprocess.call(['xdg-open', self.download_dir])
            except Exception as e:
                messagebox.showerror("Error", f"Could not open folder: {str(e)}")
        
        btn_frame = tk.Frame(dialog, bg=self.bg_dark)
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="Open File", command=open_file,
                 bg=self.accent, fg=self.bg_dark, font=("Arial", 11, "bold"),
                 padx=20, pady=10, cursor="hand2", relief=tk.FLAT).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Open Folder", command=open_folder,
                 bg=self.bg_light, fg=self.text_color, font=("Arial", 11, "bold"),
                 padx=20, pady=10, cursor="hand2", relief=tk.FLAT).pack(side=tk.LEFT, padx=5)
    
    def disconnect(self):
        """Disconnect from server"""
        self.running = False
        self.connected = False
        
        # End any active call
        if self.active_call:
            self.active_call.stop()
            self.active_call = None
            self.call_peer = None
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass

def main():
    root = tk.Tk()
    app = SecureChatGUI(root)
    
    def on_closing():
        if app.connected:
            if messagebox.askokcancel("Quit DartChat", "Are you sure you want to disconnect and quit?"):
                app.disconnect()
                root.destroy()
        else:
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()