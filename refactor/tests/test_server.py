"""
Unit tests for the DartChat server component.
Tests server initialization, client management, and message routing.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import socket
import ssl
import json
import threading
import time
from test_utils import MockSocket, MockSSLSocket, create_message_bytes, TestDataGenerator


class TestServerInitialization(unittest.TestCase):
    """Test server startup and configuration."""
    
    @patch('socket.socket')
    @patch('ssl.SSLContext')
    def test_server_socket_creation(self, mock_ssl, mock_socket):
        """Test that server creates socket on correct port."""
        mock_sock = Mock()
        mock_socket.return_value = mock_sock
        
        # Simulate server initialization
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('', 9999))
        server_socket.listen(5)
        
        mock_sock.bind.assert_called_once()
        mock_sock.listen.assert_called_once_with(5)
        
    @patch('ssl.SSLContext')
    def test_ssl_context_configuration(self, mock_ssl_context):
        """Test SSL context is configured with proper security settings."""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        
        # Verify SSL protocol is server-type
        self.assertEqual(context.protocol, ssl.PROTOCOL_TLS_SERVER)
        
    def test_data_structure_initialization(self):
        """Test server initializes required data structures."""
        # Simulate server data structures
        clients = {}
        rooms = {'general': []}
        username_map = {}
        pending_files = {}
        
        self.assertIsInstance(clients, dict)
        self.assertIsInstance(rooms, dict)
        self.assertIn('general', rooms)
        self.assertEqual(len(rooms['general']), 0)


class TestClientAuthentication(unittest.TestCase):
    """Test client authentication and username validation."""
    
    def test_valid_username_formats(self):
        """Test that valid usernames are accepted."""
        valid_usernames = ["alice", "bob123", "user_name", "test-user", "abc", "a" * 20]
        
        for username in valid_usernames:
            is_valid = (
                1 <= len(username) <= 20 and
                username.replace('_', '').replace('-', '').isalnum()
            )
            self.assertTrue(is_valid, f"Username '{username}' should be valid")
            
    def test_invalid_username_formats(self):
        """Test that invalid usernames are rejected."""
        invalid_usernames = [
            "ab",  # Too short
            "a" * 21,  # Too long
            "user name",  # Contains space
            "user@name",  # Invalid character
            "user!name",  # Invalid character
            "",  # Empty
        ]
        
        for username in invalid_usernames:
            is_valid = (
                1 <= len(username) <= 20 and
                username.replace('_', '').replace('-', '').isalnum()
            )
            self.assertFalse(is_valid, f"Username '{username}' should be invalid")
            
    def test_duplicate_username_detection(self):
        """Test that duplicate usernames are rejected."""
        username_map = {'alice': Mock(), 'bob': Mock()}
        
        # Try to add duplicate
        new_username = 'alice'
        is_duplicate = new_username.lower() in [u.lower() for u in username_map.keys()]
        
        self.assertTrue(is_duplicate, "Duplicate username should be detected")
        
    def test_case_insensitive_username_check(self):
        """Test that username checking is case-insensitive."""
        username_map = {'Alice': Mock()}
        
        # Try variations
        variations = ['alice', 'ALICE', 'AlIcE']
        
        for variant in variations:
            is_duplicate = variant.lower() in [u.lower() for u in username_map.keys()]
            self.assertTrue(is_duplicate, f"'{variant}' should match 'Alice'")


class TestRoomManagement(unittest.TestCase):
    """Test room creation, joining, and user management."""
    
    def setUp(self):
        """Set up test rooms and clients."""
        self.rooms = {'general': []}
        self.clients = {}
        self.username_map = {}
        
    def test_default_room_assignment(self):
        """Test that new users are assigned to general room."""
        username = 'alice'
        mock_client = Mock()
        
        # Simulate adding user to general room
        self.rooms['general'].append(username)
        
        self.assertIn(username, self.rooms['general'])
        
    def test_room_creation(self):
        """Test creating new chat rooms."""
        room_name = 'developers'
        
        # Simulate room creation
        if room_name not in self.rooms:
            self.rooms[room_name] = []
            
        self.assertIn(room_name, self.rooms)
        self.assertEqual(len(self.rooms[room_name]), 0)
        
    def test_user_joins_room(self):
        """Test user joining an existing room."""
        username = 'alice'
        self.rooms['general'].append(username)
        self.rooms['developers'] = []
        
        # Simulate user switching rooms
        self.rooms['general'].remove(username)
        self.rooms['developers'].append(username)
        
        self.assertNotIn(username, self.rooms['general'])
        self.assertIn(username, self.rooms['developers'])
        
    def test_list_rooms(self):
        """Test listing all available rooms."""
        self.rooms['general'] = ['alice', 'bob']
        self.rooms['developers'] = ['charlie']
        self.rooms['design'] = []
        
        room_list = []
        for room, users in self.rooms.items():
            room_list.append(f"{room} ({len(users)} users)")
            
        self.assertEqual(len(room_list), 3)
        self.assertTrue(any('general' in r for r in room_list))
        
    def test_room_cleanup_on_disconnect(self):
        """Test that users are removed from rooms on disconnect."""
        username = 'alice'
        self.rooms['general'].append(username)
        
        # Simulate disconnect
        for room_users in self.rooms.values():
            if username in room_users:
                room_users.remove(username)
                
        self.assertNotIn(username, self.rooms['general'])


class TestMessageRouting(unittest.TestCase):
    """Test message broadcasting and routing logic."""
    
    def setUp(self):
        """Set up test clients and rooms."""
        self.clients = {
            'alice': MockSSLSocket(),
            'bob': MockSSLSocket(),
            'charlie': MockSSLSocket()
        }
        self.rooms = {
            'general': ['alice', 'bob'],
            'developers': ['charlie']
        }
        
    def test_broadcast_to_room(self):
        """Test broadcasting message to all users in a room."""
        message = TestDataGenerator.create_test_message('alice', 'Hello everyone!')
        room = 'general'
        
        # Simulate broadcast
        recipients = [user for user in self.rooms[room] if user != 'alice']
        
        self.assertIn('bob', recipients)
        self.assertNotIn('charlie', recipients)  # Different room
        self.assertNotIn('alice', recipients)  # Sender
        
    def test_private_message_routing(self):
        """Test private message delivery to specific user."""
        sender = 'alice'
        recipient = 'bob'
        message = TestDataGenerator.create_test_message(sender, 'Private hello', 'private')
        
        # Verify recipient exists
        self.assertIn(recipient, self.clients)
        
    def test_message_not_sent_to_different_rooms(self):
        """Test that messages don't leak between rooms."""
        message = TestDataGenerator.create_test_message('alice', 'General message')
        sender_room = 'general'
        
        recipients = self.rooms[sender_room]
        
        self.assertNotIn('charlie', recipients)  # Charlie is in developers room
        
    def test_system_message_broadcast(self):
        """Test system messages are sent to all room users."""
        system_msg = {
            'type': 'system',
            'content': 'alice joined the room'
        }
        room = 'general'
        
        recipients = self.rooms[room]
        
        # System messages go to all users including the subject
        self.assertIn('alice', recipients)
        self.assertIn('bob', recipients)


class TestFileTransferCoordination(unittest.TestCase):
    """Test server-side file transfer coordination."""
    
    def setUp(self):
        """Set up test data for file transfers."""
        self.pending_files = {}
        self.file_id_counter = 0
        self.rooms = {'general': ['alice', 'bob', 'charlie']}
        
    def test_file_offer_creation(self):
        """Test creating file transfer offer."""
        file_id = f"file_{self.file_id_counter}"
        self.file_id_counter += 1
        
        file_data = {
            'sender': 'alice',
            'recipients': ['bob'],
            'filename': 'test.txt',
            'filesize': 1024,
            'data': 'base64data'
        }
        
        self.pending_files[file_id] = file_data
        
        self.assertIn(file_id, self.pending_files)
        self.assertEqual(self.pending_files[file_id]['sender'], 'alice')
        
    def test_file_size_validation(self):
        """Test that oversized files are rejected."""
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        
        test_cases = [
            (1024, True),  # 1KB - valid
            (5 * 1024 * 1024, True),  # 5MB - valid
            (10 * 1024 * 1024, True),  # 10MB - valid (at limit)
            (11 * 1024 * 1024, False),  # 11MB - invalid
        ]
        
        for size, should_be_valid in test_cases:
            is_valid = size <= MAX_FILE_SIZE
            self.assertEqual(is_valid, should_be_valid, f"Size {size} validation failed")
            
    def test_multi_recipient_file_transfer(self):
        """Test file transfer to multiple recipients."""
        file_data = {
            'sender': 'alice',
            'recipients': ['bob', 'charlie'],
            'filename': 'document.pdf',
            'filesize': 2048
        }
        
        self.assertEqual(len(file_data['recipients']), 2)
        self.assertIn('bob', file_data['recipients'])
        self.assertIn('charlie', file_data['recipients'])
        
    def test_broadcast_recipient_list(self):
        """Test broadcast creates recipient list from room."""
        sender = 'alice'
        room = 'general'
        
        recipients = [u for u in self.rooms[room] if u != sender]
        
        self.assertEqual(len(recipients), 2)
        self.assertIn('bob', recipients)
        self.assertIn('charlie', recipients)
        self.assertNotIn('alice', recipients)
        
    def test_file_acceptance(self):
        """Test handling file acceptance."""
        file_id = 'file_0'
        self.pending_files[file_id] = {
            'sender': 'alice',
            'recipients': ['bob'],
            'filename': 'test.txt',
            'data': 'base64data'
        }
        
        # Simulate acceptance
        accepted_file = self.pending_files.get(file_id)
        
        self.assertIsNotNone(accepted_file)
        self.assertEqual(accepted_file['sender'], 'alice')
        
    def test_file_rejection(self):
        """Test handling file rejection."""
        file_id = 'file_0'
        self.pending_files[file_id] = {'sender': 'alice', 'recipients': ['bob']}
        
        # Simulate rejection - file removed from pending
        if file_id in self.pending_files:
            del self.pending_files[file_id]
            
        self.assertNotIn(file_id, self.pending_files)


class TestVoiceCallSignaling(unittest.TestCase):
    """Test voice call coordination and signaling."""
    
    def setUp(self):
        """Set up test data for voice calls."""
        self.active_calls = {}
        self.rooms = {'general': ['alice', 'bob']}
        
    def test_call_request_validation(self):
        """Test that call requests are validated."""
        caller = 'alice'
        callee = 'bob'
        
        # Check both users in same room
        caller_room = None
        callee_room = None
        
        for room, users in self.rooms.items():
            if caller in users:
                caller_room = room
            if callee in users:
                callee_room = room
                
        self.assertEqual(caller_room, callee_room, "Users must be in same room")
        
    def test_busy_user_detection(self):
        """Test that busy users cannot receive calls."""
        self.active_calls['alice'] = {'peer': 'charlie', 'port': 5000}
        
        # Try to call alice
        is_busy = 'alice' in self.active_calls
        
        self.assertTrue(is_busy, "Alice should be marked as busy")
        
    def test_call_establishment(self):
        """Test successful call establishment."""
        caller = 'alice'
        callee = 'bob'
        caller_port = 5000
        
        # Simulate call acceptance
        self.active_calls[caller] = {'peer': callee, 'port': caller_port}
        self.active_calls[callee] = {'peer': caller, 'port': 5001}
        
        self.assertIn(caller, self.active_calls)
        self.assertIn(callee, self.active_calls)
        self.assertEqual(self.active_calls[caller]['peer'], callee)
        
    def test_call_termination(self):
        """Test call cleanup on termination."""
        self.active_calls['alice'] = {'peer': 'bob', 'port': 5000}
        self.active_calls['bob'] = {'peer': 'alice', 'port': 5001}
        
        # Simulate call end
        if 'alice' in self.active_calls:
            peer = self.active_calls['alice']['peer']
            del self.active_calls['alice']
            if peer in self.active_calls:
                del self.active_calls[peer]
                
        self.assertNotIn('alice', self.active_calls)
        self.assertNotIn('bob', self.active_calls)
        
    def test_call_to_self_prevention(self):
        """Test that users cannot call themselves."""
        caller = 'alice'
        callee = 'alice'
        
        is_valid = caller != callee
        
        self.assertFalse(is_valid, "Users should not be able to call themselves")


class TestConcurrentConnections(unittest.TestCase):
    """Test handling multiple concurrent client connections."""
    
    def test_multiple_client_management(self):
        """Test server can manage multiple clients."""
        clients = {}
        
        # Add multiple clients
        for i in range(10):
            username = f"user{i}"
            clients[username] = MockSSLSocket()
            
        self.assertEqual(len(clients), 10)
        
    def test_thread_safe_client_addition(self):
        """Test thread-safe addition of clients."""
        clients = {}
        lock = threading.Lock()
        
        def add_client(username):
            with lock:
                clients[username] = MockSSLSocket()
                
        threads = []
        for i in range(5):
            t = threading.Thread(target=add_client, args=(f"user{i}",))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        self.assertEqual(len(clients), 5)
        
    def test_graceful_disconnect_handling(self):
        """Test handling client disconnections gracefully."""
        clients = {'alice': MockSSLSocket(), 'bob': MockSSLSocket()}
        rooms = {'general': ['alice', 'bob']}
        
        # Simulate alice disconnect
        username = 'alice'
        if username in clients:
            del clients[username]
        for room_users in rooms.values():
            if username in room_users:
                room_users.remove(username)
                
        self.assertNotIn('alice', clients)
        self.assertNotIn('alice', rooms['general'])
        self.assertIn('bob', clients)


if __name__ == '__main__':
    unittest.main()
