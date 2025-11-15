"""
Chat UI Module
Command-line interface for the P2P chat application
"""
import sys
import threading
import time
from generate_certificates import generate_self_signed_cert
from p2p_client import P2PClient

class ChatUI:
    """
    Command-line interface for P2P chat
    """
    
    def __init__(self):
        self.client = None
        self.current_peer = None
        self.connected_peers = set()
        
    def start(self):
        """Start the chat UI"""
        print("=" * 60)
        print("🔐 SECURE P2P CHAT APPLICATION")
        print("=" * 60)
        print()
        
        # Get username
        username = input("Enter your username: ").strip()
        if not username:
            print("❌ Username cannot be empty")
            return
        
        # Get listen port
        try:
            listen_port = int(input("Enter listen port (e.g., 5001): ").strip())
        except ValueError:
            print("❌ Invalid port number")
            return
        
        # Get discovery server
        discovery_input = input("Discovery server (default: localhost:9000): ").strip()
        if not discovery_input:
            discovery_server = ("localhost", 9000)
        else:
            try:
                host, port = discovery_input.split(":")
                discovery_server = (host, int(port))
            except:
                print("❌ Invalid discovery server format")
                return
        
        print("\n🔑 Generating TLS certificates...")
        cert_path, key_path = generate_self_signed_cert(common_name=username)
        
        print(f"\n🚀 Starting P2P client for {username}...")
        self.client = P2PClient(
            username=username,
            listen_port=listen_port,
            cert_path=cert_path,
            key_path=key_path,
            discovery_server=discovery_server
        )
        
        # Register callbacks
        self.client.on_message(self._on_message)
        self.client.on_connection_change(self._on_connection_change)
        
        if not self.client.start():
            print("❌ Failed to start P2P client")
            return
        
        print("\n✅ Connected to P2P network!")
        self._show_help()
        
        # Command loop
        self._command_loop()
    
    def _on_message(self, peer_username, text, timestamp):
        """Handle incoming message"""
        print(f"\n💬 [{peer_username}]: {text}")
        self._show_prompt()
    
    def _on_connection_change(self, peer_username, connected):
        """Handle connection status change"""
        if connected:
            self.connected_peers.add(peer_username)
            print(f"\n✅ {peer_username} connected")
        else:
            self.connected_peers.discard(peer_username)
            print(f"\n❌ {peer_username} disconnected")
        self._show_prompt()
    
    def _show_help(self):
        """Display help message"""
        print("\n📋 COMMANDS:")
        print("  /list          - List available peers")
        print("  /connect <user> - Connect to a peer")
        print("  /chat <user>   - Start chatting with a peer")
        print("  /peers         - Show connected peers")
        print("  /help          - Show this help")
        print("  /quit          - Exit application")
        print("\nOnce chatting with a peer, type messages directly.")
        print("Use /chat <user> to switch to another peer.\n")
    
    def _show_prompt(self):
        """Display command prompt"""
        if self.current_peer:
            print(f"\n[Chatting with {self.current_peer}] > ", end="", flush=True)
        else:
            print("\n> ", end="", flush=True)
    
    def _command_loop(self):
        """Main command loop"""
        while True:
            try:
                self._show_prompt()
                command = input().strip()
                
                if not command:
                    continue
                
                if command.startswith("/"):
                    self._handle_command(command)
                elif self.current_peer:
                    self._send_message(command)
                else:
                    print("⚠️  No peer selected. Use /chat <username> to start chatting")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Exiting...")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
        
        if self.client:
            self.client.stop()
    
    def _handle_command(self, command):
        """Handle user commands"""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else None
        
        if cmd == "/list":
            self._list_peers()
        elif cmd == "/connect":
            if arg:
                self._connect_to_peer(arg)
            else:
                print("⚠️  Usage: /connect <username>")
        elif cmd == "/chat":
            if arg:
                self._start_chat(arg)
            else:
                print("⚠️  Usage: /chat <username>")
        elif cmd == "/peers":
            self._show_connected_peers()
        elif cmd == "/help":
            self._show_help()
        elif cmd == "/quit":
            print("\n👋 Goodbye!")
            sys.exit(0)
        else:
            print(f"⚠️  Unknown command: {cmd}")
            print("Type /help for available commands")
    
    def _list_peers(self):
        """List available peers"""
        print("\n🔍 Discovering peers...")
        peers = self.client.discover_peers()
        
        if not peers:
            print("No peers available")
            return
        
        print("\n📋 AVAILABLE PEERS:")
        for peer in peers:
            status = "✅ Connected" if peer["username"] in self.connected_peers else "⭕ Not connected"
            print(f"  • {peer['username']} ({peer['ip']}:{peer['port']}) - {status}")
    
    def _connect_to_peer(self, username):
        """Connect to a peer"""
        if username in self.connected_peers:
            print(f"✅ Already connected to {username}")
            return
        
        print(f"\n🔗 Connecting to {username}...")
        peers = self.client.discover_peers()
        
        peer = next((p for p in peers if p["username"] == username), None)
        if not peer:
            print(f"❌ Peer {username} not found")
            return
        
        success = self.client.connect_to_peer(
            peer["username"],
            peer["ip"],
            peer["port"]
        )
        
        if success:
            print(f"✅ Connected to {username}")
        else:
            print(f"❌ Failed to connect to {username}")
    
    def _start_chat(self, username):
        """Start chatting with a peer"""
        if username not in self.connected_peers:
            print(f"⚠️  Not connected to {username}. Connecting...")
            self._connect_to_peer(username)
            time.sleep(1)  # Wait for connection
            
            if username not in self.connected_peers:
                print(f"❌ Could not establish connection with {username}")
                return
        
        self.current_peer = username
        print(f"\n💬 Now chatting with {username}")
        print("Type your messages below. Use /chat <user> to switch peers.")
    
    def _send_message(self, text):
        """Send message to current peer"""
        if not self.current_peer:
            print("⚠️  No peer selected")
            return
        
        success = self.client.send_message(self.current_peer, text)
        if not success:
            print(f"❌ Failed to send message to {self.current_peer}")
    
    def _show_connected_peers(self):
        """Show connected peers"""
        if not self.connected_peers:
            print("\n⚠️  No connected peers")
            return
        
        print("\n✅ CONNECTED PEERS:")
        for peer in self.connected_peers:
            marker = "💬" if peer == self.current_peer else "  "
            print(f"  {marker} {peer}")

if __name__ == "__main__":
    ui = ChatUI()
    ui.start()
