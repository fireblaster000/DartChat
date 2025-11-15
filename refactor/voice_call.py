"""
Voice Call Module - UDP-based real-time audio streaming
Handles audio capture, streaming, and playback for 1-on-1 calls
"""
import pyaudio
import socket
import threading
import struct
import time
from typing import Optional, Callable

class VoiceCall:
    """Manages a single voice call session"""
    
    def __init__(self, peer_ip: str, peer_port: int, local_port: int):
        """
        Initialize voice call
        
        Args:
            peer_ip: IP address of the other person
            peer_port: UDP port where peer is listening
            local_port: UDP port to listen on for incoming audio
        """
        # Audio configuration
        self.CHUNK = 1024  # Frames per buffer
        self.FORMAT = pyaudio.paInt16  # 16-bit audio
        self.CHANNELS = 1  # Mono
        self.RATE = 44100  # Sample rate
        
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
        
        # Callbacks
        self.on_error: Optional[Callable] = None
        
    def start(self):
        """Start the voice call"""
        if self.is_active:
            print("[!] Call already active")
            return False
        
        try:
            print(f"[*] Starting voice call...")
            print(f"[*] Local port: {self.local_port}")
            print(f"[*] Peer: {self.peer_ip}:{self.peer_port}")
            
            # Initialize PyAudio
            self.audio = pyaudio.PyAudio()
            
            # Open audio input stream (microphone)
            self.input_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            
            # Open audio output stream (speakers)
            self.output_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK
            )
            
            # Create UDP socket for sending audio
            self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Create UDP socket for receiving audio
            self.recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.recv_socket.bind(('0.0.0.0', self.local_port))
            self.recv_socket.settimeout(0.1)  # Non-blocking with timeout
            
            self.is_active = True
            
            # Start audio streaming threads
            self.send_thread = threading.Thread(target=self._send_audio, daemon=True)
            self.recv_thread = threading.Thread(target=self._receive_audio, daemon=True)
            
            self.send_thread.start()
            self.recv_thread.start()
            
            print("[✓] Voice call started!")
            return True
            
        except Exception as e:
            print(f"[!] Error starting call: {e}")
            self.stop()
            if self.on_error:
                self.on_error(str(e))
            return False
    
    def _send_audio(self):
        """Thread function: Capture audio and send via UDP"""
        print("[*] Audio sending thread started")
        sequence_number = 0
        
        while self.is_active:
            try:
                if not self.is_muted:
                    # Read audio data from microphone
                    data = self.input_stream.read(self.CHUNK, exception_on_overflow=False)
                    
                    # Create packet: [sequence_number (4 bytes)][audio_data]
                    packet = struct.pack('I', sequence_number) + data
                    
                    # Send to peer
                    self.send_socket.sendto(packet, (self.peer_ip, self.peer_port))
                    
                    sequence_number += 1
                else:
                    # If muted, send silence
                    silence = b'\x00' * (self.CHUNK * 2)  # 2 bytes per sample
                    packet = struct.pack('I', sequence_number) + silence
                    self.send_socket.sendto(packet, (self.peer_ip, self.peer_port))
                    sequence_number += 1
                    time.sleep(0.02)  # Small delay when muted
                    
            except Exception as e:
                if self.is_active:  # Only log if not intentionally stopped
                    print(f"[!] Send error: {e}")
                break
        
        print("[*] Audio sending thread stopped")
    
    def _receive_audio(self):
        """Thread function: Receive audio via UDP and play"""
        print("[*] Audio receiving thread started")
        
        while self.is_active:
            try:
                # Receive packet
                packet, addr = self.recv_socket.recvfrom(4096)
                
                # Extract sequence number and audio data
                if len(packet) > 4:
                    sequence_number = struct.unpack('I', packet[:4])[0]
                    audio_data = packet[4:]
                    
                    # Play audio through speakers
                    self.output_stream.write(audio_data)
                    
            except socket.timeout:
                # Timeout is expected, continue loop
                continue
            except Exception as e:
                if self.is_active:
                    print(f"[!] Receive error: {e}")
                break
        
        print("[*] Audio receiving thread stopped")
    
    def toggle_mute(self):
        """Toggle microphone mute"""
        self.is_muted = not self.is_muted
        status = "MUTED" if self.is_muted else "UNMUTED"
        print(f"[*] Microphone {status}")
        return self.is_muted
    
    def stop(self):
        """Stop the voice call and cleanup resources"""
        if not self.is_active:
            return
        
        print("[*] Stopping voice call...")
        self.is_active = False
        
        # Wait for threads to finish
        if self.send_thread and self.send_thread.is_alive():
            self.send_thread.join(timeout=1)
        if self.recv_thread and self.recv_thread.is_alive():
            self.recv_thread.join(timeout=1)
        
        # Close audio streams
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
        
        # Terminate PyAudio
        if self.audio:
            self.audio.terminate()
        
        # Close sockets
        if self.send_socket:
            self.send_socket.close()
        if self.recv_socket:
            self.recv_socket.close()
        
        print("[✓] Voice call stopped")

# Simple test function
def test_voice_call():
    """Test voice call between two instances on same machine"""
    import sys
    
    print("="*60)
    print("VOICE CALL TEST")
    print("="*60)
    print("\nThis will test voice call on the same machine")
    print("You need to run this script TWICE in different terminals\n")
    
    mode = input("Are you [1] Caller or [2] Receiver? ").strip()
    
    if mode == '1':
        print("\n[CALLER MODE]")
        peer_ip = input("Receiver's IP [localhost]: ").strip() or "localhost"
        peer_port = int(input("Receiver's port [5001]: ").strip() or "5001")
        local_port = int(input("Your listening port [5000]: ").strip() or "5000")
        
        print(f"\n[*] Starting call to {peer_ip}:{peer_port}")
        print(f"[*] Listening on port {local_port}")
        
    elif mode == '2':
        print("\n[RECEIVER MODE]")
        peer_ip = input("Caller's IP [localhost]: ").strip() or "localhost"
        peer_port = int(input("Caller's port [5000]: ").strip() or "5000")
        local_port = int(input("Your listening port [5001]: ").strip() or "5001")
        
        print(f"\n[*] Waiting for call from {peer_ip}:{peer_port}")
        print(f"[*] Listening on port {local_port}")
    else:
        print("Invalid choice!")
        return
    
    call = VoiceCall(peer_ip, peer_port, local_port)
    
    if call.start():
        print("\n✓ Call active! Speak into your microphone.")
        print("\nCommands:")
        print("  m - Toggle mute")
        print("  q - End call")
        
        try:
            while call.is_active:
                cmd = input("\n> ").strip().lower()
                
                if cmd == 'm':
                    is_muted = call.toggle_mute()
                    print(f"Microphone: {'MUTED' if is_muted else 'UNMUTED'}")
                
                elif cmd == 'q':
                    print("Ending call...")
                    break
                
                elif cmd == '':
                    continue
                
                else:
                    print("Unknown command. Use 'm' to mute or 'q' to quit")
        
        except KeyboardInterrupt:
            print("\n\nCall interrupted")
        
        finally:
            call.stop()
    
    else:
        print("Failed to start call")

if __name__ == "__main__":
    test_voice_call()