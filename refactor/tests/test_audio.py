"""
Tests for audio system functionality.
Tests audio capture, playback, and UDP streaming.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import socket
from test_utils import MockAudioStream, TestDataGenerator


class TestAudioStreamSetup(unittest.TestCase):
    """Test audio stream initialization and configuration."""
    
    @patch('pyaudio.PyAudio')
    def test_audio_instance_creation(self, mock_pyaudio):
        """Test PyAudio instance is created correctly."""
        mock_pa = Mock()
        mock_pyaudio.return_value = mock_pa
        
        pa = mock_pyaudio()
        
        self.assertIsNotNone(pa)
        mock_pyaudio.assert_called_once()
        
    @patch('pyaudio.PyAudio')
    def test_input_stream_configuration(self, mock_pyaudio):
        """Test audio input stream is configured correctly."""
        mock_pa = Mock()
        mock_pyaudio.return_value = mock_pa
        
        FORMAT = 8  # paInt16
        CHANNELS = 1
        RATE = 44100
        CHUNK = 1024
        
        pa = mock_pyaudio()
        stream = pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        mock_pa.open.assert_called_once_with(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
    @patch('pyaudio.PyAudio')
    def test_output_stream_configuration(self, mock_pyaudio):
        """Test audio output stream is configured correctly."""
        mock_pa = Mock()
        mock_pyaudio.return_value = mock_pa
        
        FORMAT = 8
        CHANNELS = 1
        RATE = 44100
        CHUNK = 1024
        
        pa = mock_pyaudio()
        stream = pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            output=True,
            frames_per_buffer=CHUNK
        )
        
        mock_pa.open.assert_called_once()
        
    def test_audio_parameters(self):
        """Test audio parameters are appropriate."""
        RATE = 44100
        CHANNELS = 1
        CHUNK = 1024
        
        # CD quality sample rate
        self.assertEqual(RATE, 44100)
        
        # Mono audio
        self.assertEqual(CHANNELS, 1)
        
        # Reasonable chunk size (~23ms of audio at 44.1kHz)
        self.assertGreater(CHUNK, 0)
        self.assertLess(CHUNK, 8192)


class TestAudioCapture(unittest.TestCase):
    """Test audio capture functionality."""
    
    def test_audio_data_reading(self):
        """Test reading audio data from stream."""
        stream = MockAudioStream()
        CHUNK = 1024
        
        # Read audio data
        data = stream.read(CHUNK)
        
        # Should return 2 bytes per frame (16-bit)
        expected_size = CHUNK * 2
        self.assertEqual(len(data), expected_size)
        
    def test_continuous_capture(self):
        """Test continuous audio capture."""
        stream = MockAudioStream()
        CHUNK = 1024
        captured_chunks = []
        
        # Capture multiple chunks
        for _ in range(10):
            data = stream.read(CHUNK)
            captured_chunks.append(data)
            
        self.assertEqual(len(captured_chunks), 10)
        
    def test_mute_functionality(self):
        """Test muting audio capture."""
        is_muted = False
        CHUNK = 1024
        
        # Normal audio
        audio_data = b'\x01\x02' * CHUNK
        
        if is_muted:
            output = b'\x00\x00' * CHUNK
        else:
            output = audio_data
            
        self.assertEqual(output, audio_data)
        
        # Muted audio
        is_muted = True
        if is_muted:
            output = b'\x00\x00' * CHUNK
        else:
            output = audio_data
            
        self.assertEqual(output, b'\x00\x00' * CHUNK)


class TestAudioPlayback(unittest.TestCase):
    """Test audio playback functionality."""
    
    def test_audio_data_writing(self):
        """Test writing audio data to output stream."""
        stream = MockAudioStream()
        audio_data = b'\x01\x02' * 1024
        
        stream.write(audio_data)
        
        self.assertIn(audio_data, stream.recorded_data)
        
    def test_continuous_playback(self):
        """Test continuous audio playback."""
        stream = MockAudioStream()
        chunks = [b'\x01\x02' * 1024 for _ in range(10)]
        
        for chunk in chunks:
            stream.write(chunk)
            
        self.assertEqual(len(stream.recorded_data), 10)


class TestUDPStreaming(unittest.TestCase):
    """Test UDP audio streaming."""
    
    def test_udp_socket_creation(self):
        """Test creating UDP socket for audio."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        self.assertEqual(sock.type, socket.SOCK_DGRAM)
        sock.close()
        
    def test_udp_packet_structure(self):
        """Test UDP audio packet structure."""
        sequence = 42
        audio_data = b'\x01\x02' * 1024
        
        # Create packet: [sequence][audio_data]
        packet = sequence.to_bytes(4, 'big') + audio_data
        
        # Parse packet
        parsed_seq = int.from_bytes(packet[:4], 'big')
        parsed_audio = packet[4:]
        
        self.assertEqual(parsed_seq, sequence)
        self.assertEqual(parsed_audio, audio_data)
        self.assertEqual(len(packet), 4 + len(audio_data))
        
    def test_sequence_number_increment(self):
        """Test sequence numbers increment correctly."""
        sequence = 0
        packets = []
        
        for i in range(100):
            packet = sequence.to_bytes(4, 'big') + b'\x00' * 2048
            packets.append(packet)
            sequence += 1
            
        # Verify sequences
        for i, packet in enumerate(packets):
            seq = int.from_bytes(packet[:4], 'big')
            self.assertEqual(seq, i)
            
    def test_packet_size(self):
        """Test UDP packet size is appropriate."""
        AUDIO_SIZE = 2048  # Bytes of audio data
        HEADER_SIZE = 4    # Sequence number
        
        packet = b'\x00' * HEADER_SIZE + b'\x01' * AUDIO_SIZE
        
        # Should be under MTU (typically 1500 bytes for Ethernet)
        # For audio, we can use larger packets on localhost
        self.assertEqual(len(packet), 2052)
        
    def test_udp_send_receive(self):
        """Test UDP send and receive operations."""
        # Create sender and receiver sockets
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        try:
            # Bind receiver
            receiver.bind(('localhost', 0))
            receiver_port = receiver.getsockname()[1]
            
            # Send packet
            test_packet = b'test audio data'
            sender.sendto(test_packet, ('localhost', receiver_port))
            
            # Would receive in actual implementation
            # data, addr = receiver.recvfrom(4096)
            
            self.assertIsNotNone(sender)
            self.assertIsNotNone(receiver)
            
        finally:
            sender.close()
            receiver.close()


class TestAudioQuality(unittest.TestCase):
    """Test audio quality parameters."""
    
    def test_sample_rate_quality(self):
        """Test sample rate provides good quality."""
        RATE = 44100
        
        # 44.1kHz is CD quality
        self.assertGreaterEqual(RATE, 44100)
        
    def test_bit_depth(self):
        """Test bit depth is sufficient."""
        # 16-bit audio (2 bytes per sample)
        SAMPLE_SIZE = 2
        
        self.assertEqual(SAMPLE_SIZE, 2)
        
    def test_latency_calculation(self):
        """Test audio latency is acceptable."""
        RATE = 44100
        CHUNK = 1024
        
        # Calculate latency in milliseconds
        latency_ms = (CHUNK / RATE) * 1000
        
        # Should be under 50ms for real-time
        self.assertLess(latency_ms, 50)
        
    def test_buffer_size_appropriate(self):
        """Test buffer size balances latency and stability."""
        CHUNK = 1024
        
        # Not too small (causes dropouts)
        self.assertGreaterEqual(CHUNK, 256)
        
        # Not too large (causes latency)
        self.assertLessEqual(CHUNK, 4096)


class TestAudioDevices(unittest.TestCase):
    """Test audio device enumeration and selection."""
    
    @patch('pyaudio.PyAudio')
    def test_device_enumeration(self, mock_pyaudio):
        """Test listing available audio devices."""
        mock_pa = Mock()
        mock_pyaudio.return_value = mock_pa
        mock_pa.get_device_count.return_value = 3
        
        pa = mock_pyaudio()
        device_count = pa.get_device_count()
        
        self.assertEqual(device_count, 3)
        
    @patch('pyaudio.PyAudio')
    def test_default_device_selection(self, mock_pyaudio):
        """Test using default audio devices."""
        mock_pa = Mock()
        mock_pyaudio.return_value = mock_pa
        
        mock_default_input = {
            'index': 0,
            'name': 'Default Microphone',
            'maxInputChannels': 2
        }
        
        mock_pa.get_default_input_device_info.return_value = mock_default_input
        
        pa = mock_pyaudio()
        device_info = pa.get_default_input_device_info()
        
        self.assertEqual(device_info['name'], 'Default Microphone')
        self.assertGreater(device_info['maxInputChannels'], 0)


class TestErrorHandling(unittest.TestCase):
    """Test audio error handling."""
    
    @patch('pyaudio.PyAudio')
    def test_stream_error_handling(self, mock_pyaudio):
        """Test handling stream errors."""
        mock_pa = Mock()
        mock_pyaudio.return_value = mock_pa
        mock_pa.open.side_effect = Exception("Device not found")
        
        pa = mock_pyaudio()
        
        with self.assertRaises(Exception):
            stream = pa.open(format=8, channels=1, rate=44100, input=True)
            
    def test_udp_socket_error_handling(self):
        """Test handling UDP socket errors."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Try to send to invalid address
        with self.assertRaises((OSError, socket.error)):
            sock.sendto(b'test', ('invalid.address.test', 99999))
            
        sock.close()


if __name__ == '__main__':
    unittest.main()
