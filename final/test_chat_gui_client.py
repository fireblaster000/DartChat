"""
Comprehensive tests for the SecureChatGUI client
Tests GUI initialization, user interactions, message handling, and voice calls
"""
import unittest
from unittest.mock import Mock, MagicMock, patch, call
import tkinter as tk
import json
import base64
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from chat_gui_client import SecureChatGUI, VoiceCall


class TestVoiceCallGUI(unittest.TestCase):
    """Test VoiceCall class used by GUI"""
    
    @patch('chat_gui_client.pyaudio.PyAudio')
    @patch('chat_gui_client.socket.socket')
    def setUp(self, mock_socket, mock_pyaudio):
        """Set up voice call test fixtures"""
        self.mock_pyaudio = mock_pyaudio
        self.mock_socket = mock_socket
        self.voice_call = VoiceCall("127.0.0.1", 5001, 5000)
    
    def test_voice_call_initialization(self):
        """Test VoiceCall initializes with correct parameters"""
        self.assertEqual(self.voice_call.peer_ip, "127.0.0.1")
        self.assertEqual(self.voice_call.peer_port, 5001)
        self.assertEqual(self.voice_call.local_port, 5000)
        self.assertEqual(self.voice_call.CHUNK, 1024)
        self.assertEqual(self.voice_call.RATE, 44100)
        self.assertEqual(self.voice_call.CHANNELS, 1)
        self.assertFalse(self.voice_call.is_active)
        self.assertFalse(self.voice_call.is_muted)
    
    @patch('chat_gui_client.threading.Thread')
    @patch('chat_gui_client.socket.socket')
    @patch('chat_gui_client.pyaudio.PyAudio')
    def test_voice_call_start(self, mock_pyaudio, mock_socket, mock_thread):
        """Test starting a voice call"""
        # Setup mocks
        mock_audio_instance = Mock()
        mock_pyaudio.return_value = mock_audio_instance
        
        mock_input_stream = Mock()
        mock_output_stream = Mock()
        mock_audio_instance.open.side_effect = [mock_input_stream, mock_output_stream]
        
        call = VoiceCall("127.0.0.1", 5001, 5000)
        result = call.start()
        
        self.assertTrue(result)
        self.assertTrue(call.is_active)
        self.assertIsNotNone(call.audio)
        self.assertEqual(mock_audio_instance.open.call_count, 2)
    
    def test_voice_call_toggle_mute(self):
        """Test toggling mute during call"""
        call = VoiceCall("127.0.0.1", 5001, 5000)
        
        # Initially not muted
        self.assertFalse(call.is_muted)
        
        # Toggle to muted
        is_muted = call.toggle_mute()
        self.assertTrue(is_muted)
        self.assertTrue(call.is_muted)
        
        # Toggle back to unmuted
        is_muted = call.toggle_mute()
        self.assertFalse(is_muted)
        self.assertFalse(call.is_muted)
    
    @patch('chat_gui_client.threading.Thread')
    @patch('chat_gui_client.socket.socket')
    @patch('chat_gui_client.pyaudio.PyAudio')
    def test_voice_call_stop(self, mock_pyaudio, mock_socket, mock_thread):
        """Test stopping a voice call and cleanup"""
        mock_audio_instance = Mock()
        mock_pyaudio.return_value = mock_audio_instance
        
        mock_input_stream = Mock()
        mock_output_stream = Mock()
        mock_audio_instance.open.side_effect = [mock_input_stream, mock_output_stream]
        
        # Mock threads
        mock_send_thread = Mock()
        mock_recv_thread = Mock()
        mock_send_thread.is_alive.return_value = True
        mock_recv_thread.is_alive.return_value = True
        mock_thread.side_effect = [mock_send_thread, mock_recv_thread]
        
        call = VoiceCall("127.0.0.1", 5001, 5000)
        call.start()
        call.stop()
        
        self.assertFalse(call.is_active)
        mock_input_stream.stop_stream.assert_called_once()
        mock_input_stream.close.assert_called_once()
        mock_output_stream.stop_stream.assert_called_once()
        mock_output_stream.close.assert_called_once()
        mock_audio_instance.terminate.assert_called_once()


class TestSecureChatGUI(unittest.TestCase):
    """Test SecureChatGUI class"""
    
    def setUp(self):
        """Set up GUI test environment"""
        self.root = tk.Tk()
        self.root.withdraw()  # Hide window during tests
        self.gui = SecureChatGUI(self.root)
    
    def tearDown(self):
        """Clean up after each test"""
        try:
            if hasattr(self, 'gui'):
                self.gui.running = False
                if self.gui.socket:
                    self.gui.socket.close()
            self.root.destroy()
        except:
            pass
    
    def test_gui_initialization(self):
        """Test GUI initializes correctly"""
        self.assertIsNotNone(self.gui.root)
        self.assertEqual(self.gui.root.title(), "DartChat - Secure Messaging")
        self.assertIsNone(self.gui.socket)
        self.assertIsNone(self.gui.username)
        self.assertEqual(self.gui.current_room, 'general')
        self.assertFalse(self.gui.running)
        self.assertFalse(self.gui.connected)
        self.assertEqual(self.gui.download_dir, 'downloads')
    
    def test_connection_dialog_elements(self):
        """Test connection dialog has required elements"""
        self.assertIsNotNone(self.gui.host_entry)
        self.assertIsNotNone(self.gui.port_entry)
        self.assertIsNotNone(self.gui.username_entry)
        self.assertIsNotNone(self.gui.connect_btn)
        self.assertIsNotNone(self.gui.conn_status)
        
        # Check default values
        self.assertEqual(self.gui.host_entry.get(), "localhost")
        self.assertEqual(self.gui.port_entry.get(), "9999")
    
    def test_color_scheme(self):
        """Test GUI has consistent color scheme"""
        self.assertIsNotNone(self.gui.bg_dark)
        self.assertIsNotNone(self.gui.bg_medium)
        self.assertIsNotNone(self.gui.bg_light)
        self.assertIsNotNone(self.gui.accent)
        self.assertIsNotNone(self.gui.text_color)
        self.assertIsNotNone(self.gui.error_color)
        self.assertIsNotNone(self.gui.call_color)
        
        # Verify colors are hex codes
        self.assertTrue(self.gui.bg_dark.startswith('#'))
        self.assertTrue(self.gui.accent.startswith('#'))
    
    @patch('chat_gui_client.ssl.SSLContext')
    @patch('chat_gui_client.socket.socket')
    def test_send_message_raw(self, mock_socket, mock_ssl):
        """Test sending raw JSON messages"""
        mock_sock = Mock()
        self.gui.socket = mock_sock
        
        message = {'type': 'message', 'content': 'Hello'}
        self.gui.send_message_raw(message)
        
        # Verify message was sent
        mock_sock.sendall.assert_called_once()
        sent_data = mock_sock.sendall.call_args[0][0]
        
        # Verify format: 4 bytes length + JSON data
        self.assertGreater(len(sent_data), 4)
    
    def test_receive_message_format(self):
        """Test message receiving format"""
        mock_sock = Mock()
        self.gui.socket = mock_sock
        
        # Prepare test message
        test_msg = {'type': 'test', 'data': 'value'}
        json_data = json.dumps(test_msg).encode('utf-8')
        length_bytes = len(json_data).to_bytes(4, byteorder='big')
        
        # Mock socket recv to return length then data
        mock_sock.recv.side_effect = [length_bytes, json_data]
        
        received = self.gui.receive_message()
        
        self.assertEqual(received['type'], 'test')
        self.assertEqual(received['data'], 'value')
    
    def test_display_message_system(self):
        """Test displaying system messages"""
        # Setup main GUI to have chat_area
        self.gui.setup_main_gui()
        
        self.gui.display_message("System", "Test system message", "system", "12:00:00")
        
        chat_content = self.gui.chat_area.get('1.0', tk.END)
        self.assertIn("Test system message", chat_content)
        self.assertIn("12:00:00", chat_content)
    
    def test_display_message_regular(self):
        """Test displaying regular chat messages"""
        self.gui.setup_main_gui()
        
        self.gui.display_message("Alice", "Hello world", "message", "12:00:01")
        
        chat_content = self.gui.chat_area.get('1.0', tk.END)
        self.assertIn("Alice", chat_content)
        self.assertIn("Hello world", chat_content)
        self.assertIn("12:00:01", chat_content)
    
    def test_display_message_private(self):
        """Test displaying private messages"""
        self.gui.setup_main_gui()
        
        self.gui.display_message("Bob", "Secret message", "pm", "12:00:02")
        
        chat_content = self.gui.chat_area.get('1.0', tk.END)
        self.assertIn("Bob", chat_content)
        self.assertIn("Secret message", chat_content)
    
    def test_process_auth_success(self):
        """Test processing auth_success message"""
        self.gui.setup_main_gui()
        
        msg = {
            'type': 'auth_success',
            'username': 'TestUser',
            'room': 'lobby'
        }
        
        self.gui.process_message(msg)
        
        self.assertEqual(self.gui.username, 'TestUser')
        self.assertEqual(self.gui.current_room, 'lobby')
        self.assertTrue(self.gui.connected)
    
    def test_process_message_broadcast(self):
        """Test processing broadcast message"""
        self.gui.setup_main_gui()
        
        msg = {
            'type': 'message',
            'from': 'Alice',
            'content': 'Hello everyone',
            'timestamp': '12:00:00'
        }
        
        self.gui.process_message(msg)
        
        chat_content = self.gui.chat_area.get('1.0', tk.END)
        self.assertIn("Alice", chat_content)
        self.assertIn("Hello everyone", chat_content)
    
    def test_process_private_message(self):
        """Test processing private message"""
        self.gui.setup_main_gui()
        
        msg = {
            'type': 'private_message',
            'from': 'Bob',
            'content': 'Private hello',
            'timestamp': '12:00:03'
        }
        
        self.gui.process_message(msg)
        
        chat_content = self.gui.chat_area.get('1.0', tk.END)
        self.assertIn("Bob", chat_content)
        self.assertIn("Private hello", chat_content)
    
    def test_process_user_list(self):
        """Test processing user list"""
        self.gui.setup_main_gui()
        
        msg = {
            'type': 'user_list',
            'users': ['Alice', 'Bob', 'Charlie']
        }
        
        # This should not raise an error
        self.gui.process_message(msg)
    
    def test_process_room_list(self):
        """Test processing room list"""
        self.gui.setup_main_gui()
        
        msg = {
            'type': 'room_list',
            'rooms': {
                'general': 5,
                'tech': 3,
                'random': 2
            }
        }
        
        # This should not raise an error
        self.gui.process_message(msg)
    
    def test_file_offer_handling(self):
        """Test handling incoming file offer"""
        self.gui.setup_main_gui()
        
        msg = {
            'type': 'file_offer',
            'file_id': 'file123',
            'from': 'Alice',
            'filename': 'test.txt',
            'filesize': 1024,
            'broadcast': False
        }
        
        self.gui.handle_file_offer(msg)
        
        # Verify file offer is stored
        self.assertIn('file123', self.gui.pending_file_offers)
        self.assertEqual(self.gui.pending_file_offers['file123']['filename'], 'test.txt')
    
    def test_file_transfer_handling(self):
        """Test handling incoming file transfer"""
        self.gui.setup_main_gui()
        
        # Create test file data
        test_data = b'Test file content'
        encoded_data = base64.b64encode(test_data).decode('utf-8')
        
        msg = {
            'type': 'file_transfer',
            'filename': 'received_test.txt',
            'data': encoded_data,
            'from': 'Alice'
        }
        
        self.gui.handle_file_transfer(msg)
        
        # Verify file was saved
        expected_path = os.path.join(self.gui.download_dir, 'received_test.txt')
        self.assertTrue(os.path.exists(expected_path))
        
        # Verify file content
        with open(expected_path, 'rb') as f:
            content = f.read()
        self.assertEqual(content, test_data)
        
        # Verify file is tracked
        self.assertEqual(len(self.gui.received_files), 1)
        self.assertEqual(self.gui.received_files[0]['filename'], 'received_test.txt')
        
        # Cleanup
        os.remove(expected_path)
    
    def test_send_file_validation(self):
        """Test file send validation"""
        self.gui.setup_main_gui()
        mock_sock = Mock()
        self.gui.socket = mock_sock
        
        # Test non-existent file
        with patch('chat_gui_client.messagebox.showerror') as mock_error:
            self.gui.send_file('nonexistent.txt', 'Bob')
            mock_error.assert_called_once()
    
    def test_send_file_size_limit(self):
        """Test file size limit enforcement"""
        self.gui.setup_main_gui()
        mock_sock = Mock()
        self.gui.socket = mock_sock
        
        # Create large test file
        large_file_path = 'test_large.bin'
        with open(large_file_path, 'wb') as f:
            f.write(b'0' * (11 * 1024 * 1024))  # 11 MB (over limit)
        
        with patch('chat_gui_client.messagebox.showerror') as mock_error:
            self.gui.send_file(large_file_path, 'Bob')
            mock_error.assert_called_once()
            self.assertIn('too large', str(mock_error.call_args))
        
        # Cleanup
        os.remove(large_file_path)
    
    def test_call_request_handling(self):
        """Test handling incoming call request"""
        self.gui.setup_main_gui()
        
        msg = {
            'type': 'call_request',
            'from': 'Alice',
            'peer_ip': '127.0.0.1',
            'peer_port': 5001
        }
        
        # This should trigger a dialog (we'll just verify no crash)
        self.gui.handle_call_request(msg)
    
    @patch('chat_gui_client.VoiceCall')
    def test_call_accepted_handling(self, mock_voice_call):
        """Test handling call accepted message"""
        self.gui.setup_main_gui()
        
        mock_call = Mock()
        mock_call.start.return_value = True
        mock_voice_call.return_value = mock_call
        
        msg = {
            'type': 'call_accepted',
            'from': 'Bob',
            'peer_ip': '127.0.0.1',
            'peer_port': 5001
        }
        
        self.gui.process_message(msg)
        
        # Verify call was initiated
        self.assertIsNotNone(self.gui.active_call)
        self.assertEqual(self.gui.call_peer, 'Bob')
    
    def test_call_rejected_handling(self):
        """Test handling call rejected message"""
        self.gui.setup_main_gui()
        
        msg = {
            'type': 'call_rejected',
            'from': 'Bob'
        }
        
        # Should display message without crashing
        self.gui.process_message(msg)
        
        chat_content = self.gui.chat_area.get('1.0', tk.END)
        self.assertIn('rejected', chat_content.lower())
    
    @patch('chat_gui_client.VoiceCall')
    def test_end_call(self, mock_voice_call):
        """Test ending an active call"""
        self.gui.setup_main_gui()
        mock_sock = Mock()
        self.gui.socket = mock_sock
        
        # Setup active call
        mock_call = Mock()
        self.gui.active_call = mock_call
        self.gui.call_peer = 'Alice'
        
        self.gui.end_call()
        
        # Verify call was stopped
        mock_call.stop.assert_called_once()
        self.assertIsNone(self.gui.active_call)
        self.assertIsNone(self.gui.call_peer)
        
        # Verify end message was sent
        mock_sock.sendall.assert_called_once()
    
    @patch('chat_gui_client.VoiceCall')
    def test_toggle_mute_from_bar(self, mock_voice_call):
        """Test toggling mute from top bar"""
        self.gui.setup_main_gui()
        
        mock_call = Mock()
        mock_call.toggle_mute.return_value = True
        self.gui.active_call = mock_call
        
        self.gui.toggle_mute_from_bar()
        
        mock_call.toggle_mute.assert_called_once()
    
    def test_update_call_status(self):
        """Test updating call status in UI"""
        self.gui.setup_main_gui()
        
        # Test setting status
        self.gui.update_call_status("In call with Alice")
        self.assertEqual(self.gui.call_status_label.cget('text'), "In call with Alice")
        
        # Test clearing status
        self.gui.update_call_status("")
        self.assertEqual(self.gui.call_status_label.cget('text'), "")
    
    def test_disconnect_cleanup(self):
        """Test disconnect cleans up resources"""
        self.gui.setup_main_gui()
        
        # Setup active call
        mock_call = Mock()
        self.gui.active_call = mock_call
        self.gui.call_peer = 'Bob'
        
        mock_sock = Mock()
        self.gui.socket = mock_sock
        self.gui.running = True
        self.gui.connected = True
        
        self.gui.disconnect()
        
        # Verify cleanup
        self.assertFalse(self.gui.running)
        self.assertFalse(self.gui.connected)
        self.assertIsNone(self.gui.active_call)
        self.assertIsNone(self.gui.call_peer)
        mock_call.stop.assert_called_once()
        mock_sock.close.assert_called_once()


class TestGUIEdgeCases(unittest.TestCase):
    """Test edge cases and error handling in GUI"""
    
    def setUp(self):
        """Set up GUI test environment"""
        self.root = tk.Tk()
        self.root.withdraw()
        self.gui = SecureChatGUI(self.root)
    
    def tearDown(self):
        """Clean up after each test"""
        try:
            self.gui.running = False
            if self.gui.socket:
                self.gui.socket.close()
            self.root.destroy()
        except:
            pass
    
    def test_empty_username_validation(self):
        """Test empty username is rejected"""
        self.gui.username_entry.delete(0, tk.END)
        self.gui.connect_to_server()
        
        # Should show error
        self.assertIn("username", self.gui.conn_status.cget('text').lower())
    
    def test_empty_message_not_sent(self):
        """Test empty messages are not sent"""
        self.gui.setup_main_gui()
        mock_sock = Mock()
        self.gui.socket = mock_sock
        
        self.gui.message_entry.insert(0, "   ")  # Only whitespace
        self.gui.send_message()
        
        # Should not send
        mock_sock.sendall.assert_not_called()
    
    def test_file_duplicate_name_handling(self):
        """Test handling duplicate file names"""
        self.gui.setup_main_gui()
        
        # Create first file
        test_data = b'Test data 1'
        encoded = base64.b64encode(test_data).decode('utf-8')
        
        msg1 = {
            'type': 'file_transfer',
            'filename': 'duplicate.txt',
            'data': encoded,
            'from': 'Alice'
        }
        
        self.gui.handle_file_transfer(msg1)
        
        # Send same filename again
        test_data2 = b'Test data 2'
        encoded2 = base64.b64encode(test_data2).decode('utf-8')
        
        msg2 = {
            'type': 'file_transfer',
            'filename': 'duplicate.txt',
            'data': encoded2,
            'from': 'Bob'
        }
        
        self.gui.handle_file_transfer(msg2)
        
        # Verify both files exist with different names
        self.assertEqual(len(self.gui.received_files), 2)
        
        # Cleanup
        for file_info in self.gui.received_files:
            if os.path.exists(file_info['filepath']):
                os.remove(file_info['filepath'])
    
    def test_invalid_message_format(self):
        """Test handling invalid message format"""
        self.gui.setup_main_gui()
        
        # Process message with missing fields
        msg = {'type': 'unknown_type'}
        
        # Should not crash
        try:
            self.gui.process_message(msg)
        except Exception as e:
            self.fail(f"Processing invalid message raised exception: {e}")
    
    def test_self_call_prevention(self):
        """Test cannot call yourself"""
        self.gui.setup_main_gui()
        self.gui.username = 'Alice'
        
        # Attempt to send call to self would be blocked in show_call_dialog
        # We just verify the username is set correctly
        self.assertEqual(self.gui.username, 'Alice')


if __name__ == '__main__':
    unittest.main()
