"""
Integration tests for GUI client
Tests complete user workflows and interactions
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import tkinter as tk
import json
import time
import threading
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from chat_gui_client import SecureChatGUI, VoiceCall


class TestGUIWorkflows(unittest.TestCase):
    """Test complete GUI workflows"""
    
    def setUp(self):
        """Set up GUI test environment"""
        self.root = tk.Tk()
        self.root.withdraw()
        self.gui = SecureChatGUI(self.root)
    
    def tearDown(self):
        """Clean up after tests"""
        try:
            self.gui.running = False
            if self.gui.socket:
                self.gui.socket.close()
            self.root.destroy()
        except:
            pass
    
    @patch('chat_gui_client.ssl.SSLContext')
    @patch('chat_gui_client.socket.socket')
    @patch('chat_gui_client.threading.Thread')
    def test_complete_connection_workflow(self, mock_thread, mock_socket, mock_ssl):
        """Test complete connection workflow"""
        # Setup mocks
        mock_sock = Mock()
        mock_socket.return_value = Mock()
        mock_ssl_sock = Mock()
        mock_ssl.return_value.wrap_socket.return_value = mock_ssl_sock
        
        # Mock successful auth
        auth_request = {'type': 'auth_request'}
        auth_success = {'type': 'auth_success', 'username': 'TestUser', 'room': 'general'}
        
        mock_ssl_sock.recv.side_effect = [
            len(json.dumps(auth_request).encode()).to_bytes(4, 'big'),
            json.dumps(auth_request).encode(),
            len(json.dumps(auth_success).encode()).to_bytes(4, 'big'),
            json.dumps(auth_success).encode()
        ]
        
        # Set username
        self.gui.username_entry.delete(0, tk.END)
        self.gui.username_entry.insert(0, 'TestUser')
        
        # Should not raise exception
        self.gui.connect_to_server()
    
    def test_complete_chat_workflow(self):
        """Test complete chat workflow"""
        self.gui.setup_main_gui()
        mock_sock = Mock()
        self.gui.socket = mock_sock
        self.gui.username = 'Alice'
        self.gui.connected = True
        
        # Simulate sending message
        self.gui.message_entry.insert(0, 'Hello world')
        self.gui.send_message()
        
        # Verify message was sent
        mock_sock.sendall.assert_called_once()
        
        # Verify input was cleared
        self.assertEqual(self.gui.message_entry.get(), '')
        
        # Simulate receiving message
        msg = {
            'type': 'message',
            'from': 'Bob',
            'content': 'Hi Alice!',
            'timestamp': '12:00:00'
        }
        
        self.gui.process_message(msg)
        
        # Verify message appears in chat
        chat_content = self.gui.chat_area.get('1.0', tk.END)
        self.assertIn('Bob', chat_content)
        self.assertIn('Hi Alice!', chat_content)
    
    @patch('chat_gui_client.VoiceCall')
    def test_complete_voice_call_workflow(self, mock_voice_call):
        """Test complete voice call workflow"""
        self.gui.setup_main_gui()
        mock_sock = Mock()
        self.gui.socket = mock_sock
        self.gui.username = 'Alice'
        
        # Setup mock voice call
        mock_call = Mock()
        mock_call.start.return_value = True
        mock_call.toggle_mute.side_effect = [True, False]  # Mute then unmute
        mock_voice_call.return_value = mock_call
        
        # 1. Receive call request
        call_request = {
            'type': 'call_request',
            'from': 'Bob',
            'peer_ip': '127.0.0.1',
            'peer_port': 5001
        }
        
        self.gui.handle_call_request(call_request)
        
        # 2. Accept call (simulate)
        self.gui.process_message({
            'type': 'call_accepted',
            'from': 'Bob',
            'peer_ip': '127.0.0.1',
            'peer_port': 5001
        })
        
        # Verify call is active
        self.assertIsNotNone(self.gui.active_call)
        self.assertEqual(self.gui.call_peer, 'Bob')
        
        # 3. Toggle mute
        self.gui.toggle_mute_from_bar()
        mock_call.toggle_mute.assert_called()
        
        # 4. End call
        self.gui.end_call()
        
        # Verify cleanup
        mock_call.stop.assert_called_once()
        self.assertIsNone(self.gui.active_call)
        self.assertIsNone(self.gui.call_peer)
    
    def test_complete_file_transfer_workflow(self):
        """Test complete file transfer workflow"""
        self.gui.setup_main_gui()
        mock_sock = Mock()
        self.gui.socket = mock_sock
        self.gui.username = 'Alice'
        
        # 1. Create test file
        test_file = 'test_send.txt'
        with open(test_file, 'w') as f:
            f.write('Test file content')
        
        # 2. Send file
        self.gui.send_file(test_file, 'Bob')
        
        # Verify file send message was sent
        mock_sock.sendall.assert_called()
        
        # 3. Receive file offer
        import base64
        file_data = b'Received file content'
        encoded = base64.b64encode(file_data).decode('utf-8')
        
        file_offer = {
            'type': 'file_offer',
            'file_id': 'file123',
            'from': 'Bob',
            'filename': 'received.txt',
            'filesize': len(file_data),
            'broadcast': False
        }
        
        self.gui.handle_file_offer(file_offer)
        
        # Verify offer is tracked
        self.assertIn('file123', self.gui.pending_file_offers)
        
        # 4. Accept file (send accept message)
        self.gui.send_message_raw({'type': 'file_accept', 'file_id': 'file123'})
        
        # 5. Receive file data
        file_transfer = {
            'type': 'file_transfer',
            'filename': 'received.txt',
            'data': encoded,
            'from': 'Bob'
        }
        
        self.gui.handle_file_transfer(file_transfer)
        
        # Verify file was saved
        self.assertEqual(len(self.gui.received_files), 1)
        
        # Cleanup
        os.remove(test_file)
        for file_info in self.gui.received_files:
            if os.path.exists(file_info['filepath']):
                os.remove(file_info['filepath'])
    
    def test_room_switching_workflow(self):
        """Test room switching workflow"""
        self.gui.setup_main_gui()
        mock_sock = Mock()
        self.gui.socket = mock_sock
        self.gui.username = 'Alice'
        self.gui.current_room = 'general'
        
        # Send join room request
        self.gui.send_message_raw({'type': 'join_room', 'room': 'tech'})
        
        # Receive room change confirmation
        msg = {
            'type': 'room_changed',
            'room': 'tech'
        }
        
        self.gui.process_message(msg)
        
        # Verify room was changed
        self.assertEqual(self.gui.current_room, 'tech')
        self.assertEqual(self.gui.room_label.cget('text'), '# tech')
    
    def test_private_message_workflow(self):
        """Test private message workflow"""
        self.gui.setup_main_gui()
        mock_sock = Mock()
        self.gui.socket = mock_sock
        
        # Send private message
        self.gui.send_message_raw({
            'type': 'private_message',
            'target': 'Bob',
            'content': 'Secret message'
        })
        
        mock_sock.sendall.assert_called()
        
        # Receive private message
        pm = {
            'type': 'private_message',
            'from': 'Bob',
            'content': 'Secret reply',
            'timestamp': '12:00:00'
        }
        
        self.gui.process_message(pm)
        
        # Verify private message is displayed
        chat_content = self.gui.chat_area.get('1.0', tk.END)
        self.assertIn('Bob', chat_content)
        self.assertIn('Secret reply', chat_content)
    
    def test_multi_user_interaction(self):
        """Test interactions with multiple users"""
        self.gui.setup_main_gui()
        self.gui.username = 'Alice'
        
        # Receive messages from multiple users
        users = ['Bob', 'Charlie', 'Dave']
        
        for i, user in enumerate(users):
            msg = {
                'type': 'message',
                'from': user,
                'content': f'Hello from {user}',
                'timestamp': f'12:00:0{i}'
            }
            self.gui.process_message(msg)
        
        # Verify all messages are in chat
        chat_content = self.gui.chat_area.get('1.0', tk.END)
        for user in users:
            self.assertIn(user, chat_content)
            self.assertIn(f'Hello from {user}', chat_content)
    
    def test_error_recovery_workflow(self):
        """Test error recovery workflow"""
        self.gui.setup_main_gui()
        mock_sock = Mock()
        self.gui.socket = mock_sock
        
        # Simulate connection error
        mock_sock.sendall.side_effect = Exception("Connection lost")
        
        # Try to send message
        self.gui.send_message_raw({'type': 'message', 'content': 'Test'})
        
        # Verify disconnect was triggered
        self.assertFalse(self.gui.running)
        self.assertFalse(self.gui.connected)


if __name__ == '__main__':
    unittest.main()
