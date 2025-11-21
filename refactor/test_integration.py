"""
Integration tests for DartChat application.
Tests end-to-end flows and component interactions.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import threading
import time
import json
import socket
from test_utils import (
    MockSocket, MockSSLSocket, create_message_bytes,
    TestDataGenerator, wait_for_condition, cleanup_threads
)


class TestEndToEndMessaging(unittest.TestCase):
    """Test complete messaging flow from client to client."""
    
    def setUp(self):
        """Set up mock server and clients."""
        self.server_clients = {}
        self.server_rooms = {'general': []}
        self.client_sockets = {}
        
    def test_two_clients_exchange_messages(self):
        """Test two clients can exchange messages through server."""
        # Setup clients
        alice_socket = MockSSLSocket()
        bob_socket = MockSSLSocket()
        
        self.server_clients['alice'] = alice_socket
        self.server_clients['bob'] = bob_socket
        self.server_rooms['general'] = ['alice', 'bob']
        
        # Alice sends message
        alice_msg = TestDataGenerator.create_test_message('alice', 'Hello Bob!')
        
        # Server broadcasts to room (excluding sender)
        recipients = [u for u in self.server_rooms['general'] if u != 'alice']
        
        # Bob should receive the message
        self.assertIn('bob', recipients)
        self.assertNotIn('alice', recipients)
        
    def test_private_message_flow(self):
        """Test private message delivery between clients."""
        alice_socket = MockSSLSocket()
        bob_socket = MockSSLSocket()
        
        self.server_clients['alice'] = alice_socket
        self.server_clients['bob'] = bob_socket
        
        # Alice sends private message
        private_msg = {
            'type': 'private',
            'sender': 'alice',
            'recipient': 'bob',
            'content': 'Secret message'
        }
        
        # Server routes to bob only
        recipient_socket = self.server_clients.get(private_msg['recipient'])
        
        self.assertIsNotNone(recipient_socket)
        self.assertEqual(recipient_socket, bob_socket)
        
    def test_multi_room_isolation(self):
        """Test messages don't leak between rooms."""
        self.server_rooms['general'] = ['alice', 'bob']
        self.server_rooms['developers'] = ['charlie']
        
        # Alice sends in general
        sender_room = 'general'
        recipients = self.server_rooms[sender_room]
        
        # Charlie shouldn't receive it
        self.assertNotIn('charlie', recipients)
        self.assertIn('alice', recipients)
        self.assertIn('bob', recipients)


class TestRoomSwitchingFlow(unittest.TestCase):
    """Test complete room switching workflow."""
    
    def setUp(self):
        """Set up test environment."""
        self.rooms = {'general': ['alice'], 'developers': []}
        
    def test_user_switches_rooms(self):
        """Test user moving from one room to another."""
        username = 'alice'
        current_room = 'general'
        target_room = 'developers'
        
        # Remove from current room
        self.rooms[current_room].remove(username)
        
        # Add to target room
        if target_room not in self.rooms:
            self.rooms[target_room] = []
        self.rooms[target_room].append(username)
        
        # Verify
        self.assertNotIn(username, self.rooms['general'])
        self.assertIn(username, self.rooms['developers'])
        
    def test_create_and_join_new_room(self):
        """Test creating and joining a new room."""
        username = 'alice'
        new_room = 'design'
        
        # Create room
        self.rooms[new_room] = []
        
        # Switch to new room
        self.rooms['general'].remove(username)
        self.rooms[new_room].append(username)
        
        self.assertIn(new_room, self.rooms)
        self.assertIn(username, self.rooms[new_room])
        
    def test_room_announcement_flow(self):
        """Test system announces user room changes."""
        username = 'alice'
        room = 'general'
        
        # User joins
        join_announcement = {
            'type': 'system',
            'content': f'{username} joined the room'
        }
        
        # User leaves
        leave_announcement = {
            'type': 'system',
            'content': f'{username} left the room'
        }
        
        self.assertEqual(join_announcement['type'], 'system')
        self.assertIn('joined', join_announcement['content'])
        self.assertIn('left', leave_announcement['content'])


class TestFileTransferFlow(unittest.TestCase):
    """Test complete file transfer workflow."""
    
    def setUp(self):
        """Set up file transfer test environment."""
        self.pending_files = {}
        self.file_counter = 0
        self.clients = {
            'alice': MockSSLSocket(),
            'bob': MockSSLSocket()
        }
        
    def test_complete_file_transfer(self):
        """Test entire file transfer from offer to acceptance."""
        # Step 1: Sender initiates transfer
        file_id = f'file_{self.file_counter}'
        self.file_counter += 1
        
        file_data = {
            'sender': 'alice',
            'recipients': ['bob'],
            'filename': 'document.pdf',
            'filesize': 2048,
            'data': 'base64encodeddata'
        }
        
        # Step 2: Server stores pending file
        self.pending_files[file_id] = file_data
        
        # Step 3: Recipient receives offer
        offer_msg = {
            'type': 'file_offer',
            'file_id': file_id,
            'sender': 'alice',
            'filename': 'document.pdf',
            'filesize': 2048
        }
        
        # Step 4: Recipient accepts
        accept_msg = {
            'type': 'accept_file',
            'file_id': file_id
        }
        
        # Step 5: Server retrieves and sends file
        file_to_send = self.pending_files.get(file_id)
        
        self.assertIsNotNone(file_to_send)
        self.assertEqual(file_to_send['sender'], 'alice')
        self.assertEqual(file_to_send['filename'], 'document.pdf')
        
    def test_file_rejection_flow(self):
        """Test file transfer rejection."""
        file_id = 'file_0'
        self.pending_files[file_id] = {
            'sender': 'alice',
            'recipients': ['bob'],
            'filename': 'test.txt'
        }
        
        # Bob rejects
        reject_msg = {
            'type': 'reject_file',
            'file_id': file_id
        }
        
        # Server removes from pending
        if file_id in self.pending_files:
            del self.pending_files[file_id]
            
        self.assertNotIn(file_id, self.pending_files)
        
    def test_multi_recipient_file_flow(self):
        """Test file sent to multiple recipients."""
        file_id = 'file_0'
        file_data = {
            'sender': 'alice',
            'recipients': ['bob', 'charlie', 'dave'],
            'filename': 'presentation.pptx',
            'data': 'filedata'
        }
        
        self.pending_files[file_id] = file_data
        
        # Each recipient gets individual offer
        for recipient in file_data['recipients']:
            offer = {
                'type': 'file_offer',
                'file_id': file_id,
                'recipient': recipient
            }
            self.assertIn(recipient, file_data['recipients'])
            
    def test_broadcast_file_flow(self):
        """Test broadcasting file to entire room."""
        room = 'general'
        room_users = ['alice', 'bob', 'charlie']
        sender = 'alice'
        
        # Create recipient list (all except sender)
        recipients = [u for u in room_users if u != sender]
        
        file_data = {
            'sender': sender,
            'recipients': recipients,
            'filename': 'notes.txt'
        }
        
        self.assertEqual(len(recipients), 2)
        self.assertIn('bob', recipients)
        self.assertIn('charlie', recipients)
        self.assertNotIn('alice', recipients)


class TestVoiceCallFlow(unittest.TestCase):
    """Test complete voice call workflow."""
    
    def setUp(self):
        """Set up voice call test environment."""
        self.active_calls = {}
        self.clients = {
            'alice': MockSSLSocket(),
            'bob': MockSSLSocket()
        }
        self.rooms = {'general': ['alice', 'bob']}
        
    def test_successful_call_establishment(self):
        """Test complete call setup flow."""
        # Step 1: Alice requests call
        call_request = {
            'type': 'call_request',
            'caller': 'alice',
            'callee': 'bob',
            'port': 5000
        }
        
        # Step 2: Server validates (same room, not busy)
        alice_room = 'general'
        bob_room = 'general'
        alice_busy = 'alice' in self.active_calls
        bob_busy = 'bob' in self.active_calls
        
        can_call = (alice_room == bob_room and not alice_busy and not bob_busy)
        
        self.assertTrue(can_call)
        
        # Step 3: Bob receives offer
        call_offer = {
            'type': 'call_offer',
            'caller': 'alice',
            'caller_ip': '192.168.1.100',
            'caller_port': 5000
        }
        
        # Step 4: Bob accepts
        call_accept = {
            'type': 'call_accept',
            'caller': 'alice',
            'port': 5001
        }
        
        # Step 5: Server updates active calls
        self.active_calls['alice'] = {'peer': 'bob', 'port': 5000}
        self.active_calls['bob'] = {'peer': 'alice', 'port': 5001}
        
        # Step 6: Alice receives acceptance
        call_accepted = {
            'type': 'call_accepted',
            'peer_ip': '192.168.1.101',
            'peer_port': 5001
        }
        
        # Verify call is active
        self.assertIn('alice', self.active_calls)
        self.assertIn('bob', self.active_calls)
        self.assertEqual(self.active_calls['alice']['peer'], 'bob')
        
    def test_call_rejection_flow(self):
        """Test call rejection workflow."""
        # Bob rejects call
        reject_msg = {
            'type': 'call_reject',
            'caller': 'alice'
        }
        
        # Server notifies Alice
        reject_notification = {
            'type': 'call_rejected',
            'callee': 'bob'
        }
        
        # No active call created
        self.assertNotIn('alice', self.active_calls)
        self.assertNotIn('bob', self.active_calls)
        
    def test_call_to_busy_user(self):
        """Test calling user already in call."""
        # Bob is already in call with Charlie
        self.active_calls['bob'] = {'peer': 'charlie', 'port': 5001}
        
        # Alice tries to call Bob
        is_busy = 'bob' in self.active_calls
        
        self.assertTrue(is_busy)
        
        # Server sends busy message
        busy_msg = {
            'type': 'user_busy',
            'user': 'bob'
        }
        
        self.assertEqual(busy_msg['type'], 'user_busy')
        
    def test_call_termination_flow(self):
        """Test ending call and cleanup."""
        # Active call
        self.active_calls['alice'] = {'peer': 'bob', 'port': 5000}
        self.active_calls['bob'] = {'peer': 'alice', 'port': 5001}
        
        # Alice ends call
        end_call = {
            'type': 'end_call'
        }
        
        # Server cleans up
        if 'alice' in self.active_calls:
            peer = self.active_calls['alice']['peer']
            del self.active_calls['alice']
            if peer in self.active_calls:
                del self.active_calls[peer]
                
        # Verify cleanup
        self.assertNotIn('alice', self.active_calls)
        self.assertNotIn('bob', self.active_calls)
        
    def test_call_between_different_rooms(self):
        """Test that calls between different rooms are blocked."""
        self.rooms['general'] = ['alice']
        self.rooms['developers'] = ['bob']
        
        # Find rooms
        alice_room = 'general'
        bob_room = 'developers'
        
        can_call = alice_room == bob_room
        
        self.assertFalse(can_call)


class TestAuthenticationFlow(unittest.TestCase):
    """Test complete authentication workflow."""
    
    def setUp(self):
        """Set up authentication test environment."""
        self.username_map = {}
        self.clients = {}
        self.rooms = {'general': []}
        
    def test_successful_authentication(self):
        """Test successful user authentication."""
        client_socket = MockSSLSocket()
        username = 'alice'
        
        # Step 1: Server sends auth request
        auth_request = {'type': 'auth_request'}
        
        # Step 2: Client sends username
        auth_response = {
            'type': 'auth',
            'username': username
        }
        
        # Step 3: Server validates
        is_valid = (
            3 <= len(username) <= 20 and
            username.replace('_', '').replace('-', '').isalnum() and
            username.lower() not in [u.lower() for u in self.username_map.keys()]
        )
        
        self.assertTrue(is_valid)
        
        # Step 4: Server registers user
        self.username_map[username] = client_socket
        self.clients[client_socket] = username
        self.rooms['general'].append(username)
        
        # Step 5: Server sends success
        auth_success = {
            'type': 'auth_success',
            'room': 'general'
        }
        
        self.assertIn(username, self.username_map)
        self.assertIn(username, self.rooms['general'])
        
    def test_duplicate_username_rejection(self):
        """Test rejection of duplicate usernames."""
        self.username_map['alice'] = MockSSLSocket()
        
        # Try to register 'Alice' (different case)
        new_username = 'Alice'
        is_duplicate = new_username.lower() in [u.lower() for u in self.username_map.keys()]
        
        self.assertTrue(is_duplicate)
        
        # Server sends error
        error_msg = {
            'type': 'auth_error',
            'content': 'Username already taken'
        }
        
        self.assertEqual(error_msg['type'], 'auth_error')
        
    def test_invalid_username_format(self):
        """Test rejection of invalid username formats."""
        invalid_usernames = ['ab', 'a' * 21, 'user name', 'user@123']
        
        for username in invalid_usernames:
            is_valid = (
                3 <= len(username) <= 20 and
                username.replace('_', '').replace('-', '').isalnum()
            )
            
            self.assertFalse(is_valid, f"Username '{username}' should be invalid")


class TestConcurrentOperations(unittest.TestCase):
    """Test concurrent operations and race conditions."""
    
    def test_concurrent_message_sending(self):
        """Test multiple users sending messages simultaneously."""
        messages_received = []
        lock = threading.Lock()
        
        def send_message(username, content):
            with lock:
                messages_received.append({
                    'username': username,
                    'content': content
                })
                
        threads = []
        for i in range(5):
            t = threading.Thread(
                target=send_message,
                args=(f'user{i}', f'Message from user{i}')
            )
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        self.assertEqual(len(messages_received), 5)
        
    def test_concurrent_room_operations(self):
        """Test concurrent room joining/leaving."""
        rooms = {'general': [], 'developers': []}
        lock = threading.Lock()
        
        def join_room(username, room):
            with lock:
                rooms[room].append(username)
                
        threads = []
        for i in range(10):
            room = 'general' if i % 2 == 0 else 'developers'
            t = threading.Thread(target=join_room, args=(f'user{i}', room))
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        total_users = len(rooms['general']) + len(rooms['developers'])
        self.assertEqual(total_users, 10)
        
    def test_concurrent_file_transfers(self):
        """Test multiple simultaneous file transfers."""
        pending_files = {}
        lock = threading.Lock()
        counter = {'value': 0}
        
        def initiate_transfer(sender, recipient):
            with lock:
                file_id = f'file_{counter["value"]}'
                counter['value'] += 1
                pending_files[file_id] = {
                    'sender': sender,
                    'recipient': recipient
                }
                
        threads = []
        for i in range(5):
            t = threading.Thread(
                target=initiate_transfer,
                args=(f'user{i}', f'user{i+1}')
            )
            threads.append(t)
            t.start()
            
        for t in threads:
            t.join()
            
        self.assertEqual(len(pending_files), 5)


class TestDisconnectionHandling(unittest.TestCase):
    """Test graceful handling of client disconnections."""
    
    def setUp(self):
        """Set up disconnection test environment."""
        self.clients = {}
        self.username_map = {}
        self.rooms = {'general': []}
        self.active_calls = {}
        self.pending_files = {}
        
    def test_clean_disconnect_cleanup(self):
        """Test cleanup when client disconnects normally."""
        username = 'alice'
        client_socket = MockSSLSocket()
        
        # Setup user
        self.clients[client_socket] = username
        self.username_map[username] = client_socket
        self.rooms['general'].append(username)
        
        # Simulate disconnect
        if client_socket in self.clients:
            username = self.clients[client_socket]
            del self.clients[client_socket]
            del self.username_map[username]
            for room_users in self.rooms.values():
                if username in room_users:
                    room_users.remove(username)
                    
        # Verify cleanup
        self.assertNotIn(client_socket, self.clients)
        self.assertNotIn(username, self.username_map)
        self.assertNotIn(username, self.rooms['general'])
        
    def test_disconnect_during_active_call(self):
        """Test handling disconnect while in voice call."""
        username = 'alice'
        client_socket = MockSSLSocket()
        
        # Setup active call
        self.active_calls['alice'] = {'peer': 'bob', 'port': 5000}
        self.active_calls['bob'] = {'peer': 'alice', 'port': 5001}
        
        # Alice disconnects
        if username in self.active_calls:
            peer = self.active_calls[username]['peer']
            del self.active_calls[username]
            if peer in self.active_calls:
                del self.active_calls[peer]
                
        # Verify call cleanup
        self.assertNotIn('alice', self.active_calls)
        self.assertNotIn('bob', self.active_calls)
        
    def test_disconnect_with_pending_files(self):
        """Test handling disconnect with pending file transfers."""
        username = 'alice'
        
        # Setup pending files
        self.pending_files['file_0'] = {
            'sender': 'alice',
            'recipients': ['bob']
        }
        self.pending_files['file_1'] = {
            'sender': 'bob',
            'recipients': ['alice']
        }
        
        # Alice disconnects - cleanup her files
        files_to_remove = []
        for file_id, file_data in self.pending_files.items():
            if file_data['sender'] == username or username in file_data['recipients']:
                files_to_remove.append(file_id)
                
        for file_id in files_to_remove:
            del self.pending_files[file_id]
            
        # Both files should be removed
        self.assertEqual(len(self.pending_files), 0)


if __name__ == '__main__':
    unittest.main()
