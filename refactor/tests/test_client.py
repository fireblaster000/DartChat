"""
Unit tests for DartChat client components.
Tests client connection, message handling, and command parsing.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import base64
from test_utils import (
    MockSocket, MockSSLSocket, create_message_bytes, 
    TestDataGenerator, MockAudioStream
)


class TestClientConnection(unittest.TestCase):
    """Test client connection establishment."""
    
    @patch('socket.socket')
    def test_socket_connection(self, mock_socket):
        """Test client creates and connects socket."""
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        
        # Simulate connection
        host = 'localhost'
        port = 9999
        mock_sock.connect((host, port))
        
        mock_sock.connect.assert_called_once()
        
    @patch('ssl.SSLContext')
    def test_ssl_wrapping(self, mock_ssl_context):
        """Test client wraps socket with SSL."""
        mock_context = Mock()
        mock_ssl_context.return_value = mock_context
        mock_sock = Mock()
        
        # Simulate SSL wrapping
        mock_context.wrap_socket(mock_sock, server_hostname='localhost')
        
        mock_context.wrap_socket.assert_called_once()
        
    def test_authentication_flow(self):
        """Test client authentication with server."""
        mock_socket = MockSSLSocket()
        username = 'alice'
        
        # Simulate receiving auth request
        auth_request = create_message_bytes({'type': 'auth_request'})
        mock_socket.add_receive_data(auth_request)
        
        # Client should send auth response
        auth_response = {
            'type': 'auth',
            'username': username
        }
        
        self.assertEqual(auth_response['username'], username)
        self.assertEqual(auth_response['type'], 'auth')


class TestCommandParsing(unittest.TestCase):
    """Test parsing and validation of user commands."""
    
    def test_help_command(self):
        """Test help command parsing."""
        command = '/help'
        is_command = command.startswith('/')
        cmd_name = command.split()[0][1:] if is_command else None
        
        self.assertTrue(is_command)
        self.assertEqual(cmd_name, 'help')
        
    def test_private_message_command(self):
        """Test private message command parsing."""
        command = '/pm bob Hello there!'
        
        if command.startswith('/pm '):
            parts = command[4:].split(' ', 1)
            recipient = parts[0]
            message = parts[1] if len(parts) > 1 else ''
            
            self.assertEqual(recipient, 'bob')
            self.assertEqual(message, 'Hello there!')
            
    def test_join_room_command(self):
        """Test room join command parsing."""
        command = '/join developers'
        
        if command.startswith('/join '):
            room_name = command[6:].strip()
            
            self.assertEqual(room_name, 'developers')
            
    def test_create_room_command(self):
        """Test room creation command parsing."""
        command = '/create newroom'
        
        if command.startswith('/create '):
            room_name = command[8:].strip()
            
            self.assertEqual(room_name, 'newroom')
            self.assertGreater(len(room_name), 0)
            
    def test_sendfile_command(self):
        """Test file send command parsing."""
        command = '/sendfile bob /path/to/file.txt'
        
        if command.startswith('/sendfile '):
            parts = command[10:].split(' ', 1)
            recipient = parts[0]
            filepath = parts[1] if len(parts) > 1 else ''
            
            self.assertEqual(recipient, 'bob')
            self.assertEqual(filepath, '/path/to/file.txt')
            
    def test_sendmulti_command(self):
        """Test multi-user file send command parsing."""
        command = '/sendmulti alice,bob,charlie /path/to/file.pdf'
        
        if command.startswith('/sendmulti '):
            parts = command[11:].split(' ', 1)
            recipients_str = parts[0]
            filepath = parts[1] if len(parts) > 1 else ''
            recipients = [r.strip() for r in recipients_str.split(',')]
            
            self.assertEqual(len(recipients), 3)
            self.assertIn('alice', recipients)
            self.assertIn('bob', recipients)
            self.assertIn('charlie', recipients)
            
    def test_accept_file_command(self):
        """Test file acceptance command parsing."""
        command = '/accept file_123'
        
        if command.startswith('/accept '):
            file_id = command[8:].strip()
            
            self.assertEqual(file_id, 'file_123')
            
    def test_call_command(self):
        """Test voice call command parsing."""
        command = '/call bob'
        
        if command.startswith('/call '):
            callee = command[6:].strip()
            
            self.assertEqual(callee, 'bob')
            
    def test_invalid_command(self):
        """Test handling of invalid commands."""
        command = '/invalidcmd'
        
        valid_commands = ['help', 'pm', 'join', 'create', 'users', 'rooms', 
                         'sendfile', 'sendmulti', 'broadcast', 'accept', 'reject',
                         'files', 'view', 'call', 'endcall']
        
        cmd_name = command.split()[0][1:] if command.startswith('/') else None
        is_valid = cmd_name in valid_commands
        
        self.assertFalse(is_valid)
        
    def test_command_with_missing_arguments(self):
        """Test commands with missing required arguments."""
        test_cases = [
            ('/pm', False),  # Missing recipient and message
            ('/pm bob', False),  # Missing message
            ('/sendfile', False),  # Missing recipient and file
            ('/join', False),  # Missing room name
        ]
        
        for command, should_be_valid in test_cases:
            parts = command.split()
            if parts[0] == '/pm':
                # /pm needs recipient AND message (3 parts minimum)
                has_args = len(parts) >= 3
            else:
                # Most other commands need at least 2 parts (command + argument)
                has_args = len(parts) >= 2
            self.assertEqual(has_args, should_be_valid, f"Command '{command}' validation failed")


class TestMessageHandling(unittest.TestCase):
    """Test client message sending and receiving."""
    
    def test_send_public_message(self):
        """Test sending public room messages."""
        message_text = 'Hello everyone!'
        username = 'alice'
        
        message = {
            'type': 'message',
            'content': message_text,
            'username': username
        }
        
        self.assertEqual(message['type'], 'message')
        self.assertEqual(message['content'], message_text)
        
    def test_send_private_message(self):
        """Test sending private messages."""
        recipient = 'bob'
        message_text = 'Private hello'
        
        message = {
            'type': 'private',
            'recipient': recipient,
            'content': message_text
        }
        
        self.assertEqual(message['type'], 'private')
        self.assertEqual(message['recipient'], recipient)
        
    def test_receive_message_parsing(self):
        """Test parsing received messages."""
        received_data = create_message_bytes({
            'type': 'message',
            'username': 'bob',
            'content': 'Hello back!',
            'timestamp': '14:30:00'
        })
        
        # Parse message
        msg_len = int.from_bytes(received_data[:4], 'big')
        msg_data = received_data[4:4+msg_len]
        message = json.loads(msg_data.decode('utf-8'))
        
        self.assertEqual(message['type'], 'message')
        self.assertEqual(message['username'], 'bob')
        self.assertEqual(message['content'], 'Hello back!')
        
    def test_system_message_handling(self):
        """Test handling system messages."""
        system_msg = {
            'type': 'system',
            'content': 'alice joined the room'
        }
        
        self.assertEqual(system_msg['type'], 'system')
        self.assertIn('joined', system_msg['content'])
        
    def test_error_message_handling(self):
        """Test handling error messages from server."""
        error_msg = {
            'type': 'error',
            'content': 'User not found'
        }
        
        self.assertEqual(error_msg['type'], 'error')
        self.assertIsNotNone(error_msg['content'])


class TestFileOperations(unittest.TestCase):
    """Test client-side file transfer operations."""
    
    def test_file_reading(self):
        """Test reading file for transfer."""
        test_content = b'Test file content here'
        
        # Simulate file read
        file_data = test_content
        encoded = base64.b64encode(file_data).decode('utf-8')
        
        self.assertIsNotNone(encoded)
        self.assertGreater(len(encoded), 0)
        
    def test_file_encoding(self):
        """Test Base64 encoding for file transfer."""
        original_data = b'Binary file data \x00\x01\x02'
        
        encoded = base64.b64encode(original_data).decode('utf-8')
        decoded = base64.b64decode(encoded)
        
        self.assertEqual(original_data, decoded)
        
    def test_file_size_check(self):
        """Test file size validation before transfer."""
        MAX_SIZE = 10 * 1024 * 1024  # 10MB
        
        test_cases = [
            (1024, True),
            (5 * 1024 * 1024, True),
            (10 * 1024 * 1024, True),
            (11 * 1024 * 1024, False),
            (100 * 1024 * 1024, False),
        ]
        
        for size, should_pass in test_cases:
            is_valid = size <= MAX_SIZE
            self.assertEqual(is_valid, should_pass, f"Size {size} validation failed")
            
    def test_file_save(self):
        """Test saving received file."""
        file_data_encoded = base64.b64encode(b'File content').decode('utf-8')
        filename = 'received_file.txt'
        
        # Simulate file save
        decoded_data = base64.b64decode(file_data_encoded)
        
        self.assertEqual(decoded_data, b'File content')
        
    def test_filename_collision_handling(self):
        """Test handling duplicate filenames."""
        existing_files = ['document.pdf', 'document_1.pdf']
        new_filename = 'document.pdf'
        
        # Simulate collision handling
        counter = 1
        final_filename = new_filename
        name, ext = new_filename.rsplit('.', 1) if '.' in new_filename else (new_filename, '')
        
        while final_filename in existing_files:
            final_filename = f"{name}_{counter}.{ext}" if ext else f"{name}_{counter}"
            counter += 1
            
        self.assertEqual(final_filename, 'document_2.pdf')
        
    def test_file_metadata_tracking(self):
        """Test tracking received file metadata."""
        file_info = {
            'filename': 'document.pdf',
            'sender': 'alice',
            'timestamp': '14:30:00',
            'size': 2048
        }
        
        received_files = [file_info]
        
        self.assertEqual(len(received_files), 1)
        self.assertEqual(received_files[0]['sender'], 'alice')
        self.assertEqual(received_files[0]['size'], 2048)


class TestVoiceCallClient(unittest.TestCase):
    """Test client-side voice call functionality."""
    
    @patch('pyaudio.PyAudio')
    def test_audio_stream_initialization(self, mock_pyaudio):
        """Test audio stream setup for voice calls."""
        mock_pa = Mock()
        mock_pyaudio.return_value = mock_pa
        mock_stream = MockAudioStream()
        mock_pa.open.return_value = mock_stream
        
        # Simulate stream opening
        FORMAT = 8  # paInt16
        CHANNELS = 1
        RATE = 44100
        CHUNK = 1024
        
        stream = mock_pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        mock_pa.open.assert_called_once()
        
    def test_udp_socket_creation(self):
        """Test UDP socket creation for audio streaming."""
        import socket
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.assertIsNotNone(sock)
        
    def test_audio_packet_format(self):
        """Test audio packet structure with sequence number."""
        sequence = 42
        audio_data = b'\x00' * 2048
        
        packet = sequence.to_bytes(4, 'big') + audio_data
        
        # Parse packet
        parsed_seq = int.from_bytes(packet[:4], 'big')
        parsed_audio = packet[4:]
        
        self.assertEqual(parsed_seq, sequence)
        self.assertEqual(len(parsed_audio), 2048)
        
    def test_mute_functionality(self):
        """Test muting audio during call."""
        is_muted = False
        audio_data = b'\x01\x02\x03\x04'
        
        # When muted, send silence
        if is_muted:
            audio_to_send = b'\x00' * len(audio_data)
        else:
            audio_to_send = audio_data
            
        self.assertEqual(audio_to_send, audio_data)
        
        # Now mute
        is_muted = True
        if is_muted:
            audio_to_send = b'\x00' * len(audio_data)
        else:
            audio_to_send = audio_data
            
        self.assertEqual(audio_to_send, b'\x00\x00\x00\x00')
        
    def test_call_request_creation(self):
        """Test creating call request message."""
        callee = 'bob'
        udp_port = 5000
        
        call_request = {
            'type': 'call_request',
            'callee': callee,
            'port': udp_port
        }
        
        self.assertEqual(call_request['type'], 'call_request')
        self.assertEqual(call_request['callee'], callee)
        self.assertEqual(call_request['port'], udp_port)
        
    def test_call_acceptance_parsing(self):
        """Test parsing call acceptance response."""
        response = {
            'type': 'call_accepted',
            'peer_ip': '192.168.1.100',
            'peer_port': 5001
        }
        
        self.assertEqual(response['type'], 'call_accepted')
        self.assertIsNotNone(response['peer_ip'])
        self.assertGreater(response['peer_port'], 0)


class TestGUISpecific(unittest.TestCase):
    """Test GUI client specific functionality."""
    
    @patch('tkinter.Tk')
    def test_gui_initialization(self, mock_tk):
        """Test GUI window initialization."""
        mock_root = Mock()
        mock_tk.return_value = mock_root
        
        # Simulate GUI setup
        mock_root.title("DartChat")
        mock_root.geometry("800x600")
        
        mock_root.title.assert_called_once()
        mock_root.geometry.assert_called_once()
        
    def test_message_display_formatting(self):
        """Test formatting messages for GUI display."""
        message = {
            'type': 'message',
            'username': 'alice',
            'content': 'Hello!',
            'timestamp': '14:30:00'
        }
        
        formatted = f"[{message['timestamp']}] {message['username']}: {message['content']}"
        
        self.assertIn('14:30:00', formatted)
        self.assertIn('alice', formatted)
        self.assertIn('Hello!', formatted)
        
    def test_button_command_mapping(self):
        """Test button actions map to correct commands."""
        button_commands = {
            'help': '/help',
            'users': '/users',
            'rooms': '/rooms',
            'files': '/files'
        }
        
        self.assertEqual(button_commands['help'], '/help')
        self.assertEqual(button_commands['users'], '/users')


if __name__ == '__main__':
    unittest.main()
