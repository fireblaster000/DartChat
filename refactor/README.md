# DartChat Test Suite

Comprehensive testing for the DartChat secure messaging application.

## Test Structure

### Unit Tests

- **test_server.py** - Server component tests
  - Server initialization and configuration
  - Client authentication and validation
  - Room management
  - Message routing
  - File transfer coordination
  - Voice call signaling
  - Concurrent connection handling

- **test_client.py** - Client component tests
  - Connection establishment
  - Command parsing and validation
  - Message handling (send/receive)
  - File operations
  - Voice call client functionality
  - GUI-specific features

- **test_security.py** - Security and encryption tests
  - TLS/SSL configuration
  - Certificate generation
  - Secure message transmission
  - Input validation and sanitization
  - Authorization checks
  - Data encoding security

- **test_audio.py** - Audio system tests
  - Audio stream setup
  - Audio capture and playback
  - UDP streaming
  - Audio quality parameters
  - Device enumeration
  - Error handling

### Integration Tests

- **test_integration.py** - End-to-end workflow tests
  - Complete messaging flows
  - Room switching workflows
  - File transfer complete flows
  - Voice call establishment and termination
  - Authentication workflows
  - Concurrent operations
  - Disconnection handling

## Running Tests

### Run All Tests
\`\`\`bash
python tests/run_all_tests.py
\`\`\`

### Run Specific Test Module
\`\`\`bash
python -m unittest tests.test_server
python -m unittest tests.test_client
python -m unittest tests.test_integration
\`\`\`

### Run Specific Test Class
\`\`\`bash
python -m unittest tests.test_server.TestServerInitialization
python -m unittest tests.test_client.TestCommandParsing
\`\`\`

### Run Specific Test Method
\`\`\`bash
python -m unittest tests.test_server.TestServerInitialization.test_server_socket_creation
\`\`\`

### Run with Verbose Output
\`\`\`bash
python -m unittest tests.test_server -v
\`\`\`

## Test Coverage

The test suite provides comprehensive coverage of:

- ✅ Server initialization and configuration
- ✅ Client connection and authentication
- ✅ Message routing and broadcasting
- ✅ Room management and switching
- ✅ File transfer coordination
- ✅ Voice call signaling
- ✅ TLS/SSL security
- ✅ Input validation
- ✅ Audio capture and playback
- ✅ UDP streaming
- ✅ Concurrent operations
- ✅ Error handling
- ✅ Graceful disconnection

## Test Utilities

**test_utils.py** provides:
- Mock socket implementations (MockSocket, MockSSLSocket)
- Mock audio stream (MockAudioStream)
- Test data generators (TestDataGenerator)
- Helper functions for testing
- Thread management utilities

## Writing New Tests

When adding new features, follow this pattern:

\`\`\`python
import unittest
from test_utils import MockSocket, TestDataGenerator

class TestNewFeature(unittest.TestCase):
    """Test description."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_data = {}
        
    def test_feature_behavior(self):
        """Test specific behavior."""
        # Arrange
        input_data = TestDataGenerator.create_test_data()
        
        # Act
        result = process_data(input_data)
        
        # Assert
        self.assertEqual(result, expected_output)
        
    def tearDown(self):
        """Clean up after tests."""
        pass
\`\`\`

## Continuous Integration

These tests are designed to run in CI/CD pipelines:

\`\`\`yaml
# Example GitHub Actions
- name: Run tests
  run: python tests/run_all_tests.py
\`\`\`

## Performance Considerations

- Tests use mocking to avoid actual network operations
- Audio tests don't require hardware devices
- Integration tests use timeouts to prevent hanging
- Concurrent tests verify thread safety

## Known Limitations

- TLS certificate tests don't generate actual certificates
- Audio tests use mock streams instead of real hardware
- UDP tests don't test actual network latency
- Some integration tests use simplified server simulation

## Troubleshooting

**Import Errors:**
\`\`\`bash
# Ensure you're in the project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
\`\`\`

**Mock Not Working:**
\`\`\`bash
# Install required packages
pip install unittest-mock
\`\`\`

**Tests Timing Out:**
- Check thread cleanup in tearDown methods
- Verify mocks are properly configured
- Increase timeout values if needed
