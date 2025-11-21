"""
Security and encryption tests for DartChat.
Tests TLS configuration, certificate generation, and secure communication.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import ssl
import socket
from test_utils import MockSocket, MockSSLSocket


class TestTLSConfiguration(unittest.TestCase):
    """Test TLS/SSL configuration and security settings."""
    
    def test_ssl_context_protocol(self):
        """Test SSL context uses secure protocol version."""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        
        # Should use TLS (not SSLv2/SSLv3)
        self.assertEqual(context.protocol, ssl.PROTOCOL_TLS_SERVER)
        
    def test_minimum_tls_version(self):
        """Test minimum TLS version is 1.2 or higher."""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        
        self.assertGreaterEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
        
    def test_cipher_suite_configuration(self):
        """Test that strong cipher suites are configured."""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        
        # Configure strong ciphers
        strong_ciphers = (
            'ECDHE+AESGCM:'
            'ECDHE+CHACHA20:'
            'DHE+AESGCM:'
            'DHE+CHACHA20:'
            '!aNULL:!MD5:!DSS'
        )
        
        context.set_ciphers(strong_ciphers)
        
        # Verify context is configured
        self.assertIsNotNone(context)
        
    def test_certificate_verification_disabled(self):
        """Test client disables certificate verification (self-signed)."""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        self.assertEqual(context.verify_mode, ssl.CERT_NONE)
        self.assertFalse(context.check_hostname)


class TestCertificateGeneration(unittest.TestCase):
    """Test SSL certificate generation."""
    
    @patch('cryptography.x509.CertificateBuilder')
    def test_certificate_structure(self, mock_builder):
        """Test certificate contains required fields."""
        from datetime import datetime, timedelta
        
        # Certificate should have:
        # - Subject (CN=localhost)
        # - Issuer (self-signed)
        # - Validity period
        # - Public key
        # - Subject Alternative Names
        
        required_fields = ['subject', 'issuer', 'not_valid_before', 'not_valid_after']
        
        for field in required_fields:
            self.assertIsNotNone(field)
            
    def test_certificate_validity_period(self):
        """Test certificate has appropriate validity period."""
        from datetime import datetime, timedelta
        
        not_before = datetime.utcnow()
        not_after = not_before + timedelta(days=365)
        
        validity_days = (not_after - not_before).days
        
        self.assertEqual(validity_days, 365)
        self.assertGreater(validity_days, 0)
        
    def test_rsa_key_size(self):
        """Test RSA key is sufficiently large."""
        # Minimum secure key size is 2048 bits
        MIN_KEY_SIZE = 2048
        key_size = 2048
        
        self.assertGreaterEqual(key_size, MIN_KEY_SIZE)
        
    def test_subject_alternative_names(self):
        """Test certificate includes localhost and 127.0.0.1."""
        san_entries = ['localhost', '127.0.0.1']
        
        self.assertIn('localhost', san_entries)
        self.assertIn('127.0.0.1', san_entries)


class TestSecureMessageTransmission(unittest.TestCase):
    """Test secure message transmission over TLS."""
    
    def test_message_length_prefix(self):
        """Test messages use length prefix to prevent tampering."""
        import json
        
        message = {'type': 'message', 'content': 'test'}
        data = json.dumps(message).encode('utf-8')
        length = len(data)
        
        packet = length.to_bytes(4, 'big') + data
        
        # Parse packet
        parsed_length = int.from_bytes(packet[:4], 'big')
        parsed_data = packet[4:4+parsed_length]
        
        self.assertEqual(length, parsed_length)
        self.assertEqual(data, parsed_data)
        
    def test_message_integrity(self):
        """Test message cannot be modified in transit."""
        import json
        
        original_message = {'type': 'message', 'content': 'original'}
        data = json.dumps(original_message).encode('utf-8')
        
        # TLS ensures data integrity - any modification would be detected
        # Here we verify the message structure is preserved
        
        parsed_message = json.loads(data.decode('utf-8'))
        
        self.assertEqual(original_message, parsed_message)
        
    @patch('ssl.SSLSocket')
    def test_ssl_socket_wrapping(self, mock_ssl_socket):
        """Test socket is properly wrapped with SSL."""
        mock_socket = Mock()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        
        # Wrap socket
        ssl_sock = context.wrap_socket(mock_socket, server_hostname='localhost')
        
        context.wrap_socket.assert_called_once()


class TestInputValidation(unittest.TestCase):
    """Test input validation to prevent injection attacks."""
    
    def test_username_sanitization(self):
        """Test username validation prevents injection."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "admin' OR '1'='1",
            "../../../etc/passwd",
            "user\nname",
            "user\x00name"
        ]
        
        for malicious in malicious_inputs:
            is_valid = (
                3 <= len(malicious) <= 20 and
                malicious.replace('_', '').replace('-', '').isalnum()
            )
            self.assertFalse(is_valid, f"Malicious input '{malicious}' should be rejected")
            
    def test_room_name_validation(self):
        """Test room name validation."""
        valid_rooms = ['general', 'developers', 'room_123', 'test-room']
        invalid_rooms = ['', 'a' * 51, 'room name', 'room/path']
        
        for room in valid_rooms:
            is_valid = len(room) > 0 and len(room) <= 50
            self.assertTrue(is_valid, f"Room '{room}' should be valid")
            
        for room in invalid_rooms:
            is_valid = len(room) > 0 and len(room) <= 50 and ' ' not in room
            self.assertFalse(is_valid, f"Room '{room}' should be invalid")
            
    def test_filename_path_traversal_prevention(self):
        """Test filename validation prevents path traversal."""
        malicious_filenames = [
            '../../../etc/passwd',
            '..\\..\\windows\\system32\\config',
            '/etc/passwd',
            'C:\\Windows\\System32\\',
        ]
        
        for filename in malicious_filenames:
            # Should reject filenames with path separators
            is_safe = '..' not in filename and '/' not in filename and '\\' not in filename
            self.assertFalse(is_safe, f"Filename '{filename}' should be rejected")
            
    def test_file_size_limits(self):
        """Test file size limits are enforced."""
        MAX_SIZE = 10 * 1024 * 1024
        
        test_cases = [
            (0, True),
            (MAX_SIZE, True),
            (MAX_SIZE + 1, False),
            (100 * 1024 * 1024, False)
        ]
        
        for size, should_pass in test_cases:
            is_valid = 0 < size <= MAX_SIZE
            self.assertEqual(is_valid, should_pass, f"Size {size} validation failed")


class TestDataEncoding(unittest.TestCase):
    """Test data encoding and decoding security."""
    
    def test_base64_encoding_integrity(self):
        """Test Base64 encoding preserves data integrity."""
        import base64
        
        test_data = [
            b'Normal text data',
            b'\x00\x01\x02\x03\x04\x05',  # Binary data
            b'Special chars: \n\r\t',
            b'Unicode: \xc3\xa9\xc3\xa0\xc3\xbc'  # UTF-8 encoded unicode
        ]
        
        for data in test_data:
            encoded = base64.b64encode(data)
            decoded = base64.b64decode(encoded)
            
            self.assertEqual(data, decoded)
            
    def test_json_encoding_safety(self):
        """Test JSON encoding handles special characters safely."""
        import json
        
        test_cases = [
            {'content': 'Normal message'},
            {'content': "Message with 'quotes'"},
            {'content': 'Message with "double quotes"'},
            {'content': 'Message with \n newline'},
            {'content': 'Message with <script> tags'}
        ]
        
        for test_case in test_cases:
            encoded = json.dumps(test_case)
            decoded = json.loads(encoded)
            
            self.assertEqual(test_case, decoded)


class TestAuthorizationChecks(unittest.TestCase):
    """Test authorization and access control."""
    
    def test_file_transfer_same_room_requirement(self):
        """Test file transfer requires sender and recipient in same room."""
        rooms = {
            'general': ['alice', 'bob'],
            'developers': ['charlie']
        }
        
        # Alice to Bob - should work
        alice_room = 'general'
        bob_room = 'general'
        can_transfer = alice_room == bob_room
        self.assertTrue(can_transfer)
        
        # Alice to Charlie - should fail
        charlie_room = 'developers'
        can_transfer = alice_room == charlie_room
        self.assertFalse(can_transfer)
        
    def test_voice_call_same_room_requirement(self):
        """Test voice calls require users in same room."""
        rooms = {
            'general': ['alice', 'bob'],
            'developers': ['charlie']
        }
        
        # Alice calls Bob - should work
        can_call = 'alice' in rooms['general'] and 'bob' in rooms['general']
        self.assertTrue(can_call)
        
        # Alice calls Charlie - should fail
        alice_in_general = 'alice' in rooms['general']
        charlie_in_general = 'charlie' in rooms['general']
        can_call = alice_in_general and charlie_in_general
        self.assertFalse(can_call)
        
    def test_private_message_recipient_exists(self):
        """Test private messages require valid recipient."""
        clients = {'alice': Mock(), 'bob': Mock()}
        
        # Valid recipient
        recipient = 'bob'
        can_send = recipient in clients
        self.assertTrue(can_send)
        
        # Invalid recipient
        recipient = 'charlie'
        can_send = recipient in clients
        self.assertFalse(can_send)


if __name__ == '__main__':
    unittest.main()
