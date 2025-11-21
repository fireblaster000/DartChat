"""
Shared testing utilities and mock objects for DartChat tests.
"""

import socket
import ssl
import json
import threading
import time
from unittest.mock import Mock, MagicMock
from io import BytesIO


class MockSocket:
    """Mock socket for testing network operations."""
    
    def __init__(self):
        self.sent_data = []
        self.receive_data = []
        self.closed = False
        self.connected = False
        
    def connect(self, address):
        self.connected = True
        
    def sendall(self, data):
        if self.closed:
            raise OSError("Socket is closed")
        self.sent_data.append(data)
        
    def recv(self, size):
        if self.closed:
            raise OSError("Socket is closed")
        if not self.receive_data:
            return b''
        data = self.receive_data.pop(0)
        return data[:size]
        
    def close(self):
        self.closed = True
        
    def settimeout(self, timeout):
        pass
        
    def add_receive_data(self, data):
        """Add data to be received by recv()."""
        self.receive_data.append(data)
        
    def get_sent_messages(self):
        """Parse sent data into JSON messages."""
        messages = []
        for data in self.sent_data:
            if len(data) > 4:
                msg_data = data[4:]  # Skip length prefix
                try:
                    messages.append(json.loads(msg_data.decode('utf-8')))
                except:
                    pass
        return messages


class MockSSLSocket(MockSocket):
    """Mock SSL socket for testing encrypted connections."""
    
    def __init__(self):
        super().__init__()
        self.ssl_wrapped = True


def create_message_bytes(message_dict):
    """Create properly formatted message bytes with length prefix."""
    data = json.dumps(message_dict).encode('utf-8')
    return len(data).to_bytes(4, 'big') + data


def create_test_server(port=9999):
    """Create a minimal test server for integration testing."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('localhost', port))
    server_socket.listen(5)
    return server_socket


class MockAudioStream:
    """Mock PyAudio stream for audio testing."""
    
    def __init__(self, rate=44100, channels=1, format=None):
        self.rate = rate
        self.channels = channels
        self.format = format
        self.is_active = False
        self.recorded_data = []
        
    def start_stream(self):
        self.is_active = True
        
    def stop_stream(self):
        self.is_active = False
        
    def close(self):
        self.is_active = False
        
    def read(self, num_frames):
        """Return mock audio data."""
        return b'\x00' * (num_frames * 2)  # 16-bit audio
        
    def write(self, data):
        """Store written audio data."""
        self.recorded_data.append(data)
        
    def is_active(self):
        return self.is_active


class TestDataGenerator:
    """Generate test data for various scenarios."""
    
    @staticmethod
    def create_test_file(size_bytes=1024):
        """Create test file content."""
        return b'Test file content ' * (size_bytes // 18)
        
    @staticmethod
    def create_test_users(count=3):
        """Create list of test usernames."""
        return [f"testuser{i}" for i in range(count)]
        
    @staticmethod
    def create_test_message(username="alice", content="Hello", msg_type="message"):
        """Create test message dictionary."""
        return {
            "type": msg_type,
            "username": username,
            "content": content,
            "timestamp": "12:00:00"
        }
        
    @staticmethod
    def create_test_audio_packet(sequence=0, size=2048):
        """Create test audio packet with sequence number."""
        return sequence.to_bytes(4, 'big') + (b'\x00' * size)


def wait_for_condition(condition_func, timeout=5, interval=0.1):
    """Wait for a condition to become true with timeout."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(interval)
    return False


def cleanup_threads(threads):
    """Clean up test threads."""
    for thread in threads:
        if thread.is_alive():
            thread.join(timeout=2)
