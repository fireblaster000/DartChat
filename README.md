# 🔐 Secure P2P Chat Application

A comprehensive peer-to-peer chat application with TLS encryption, peer discovery, and secure message exchange.

## 🌟 Features

### Security
- **TLS 1.3 Encryption**: All peer-to-peer communications encrypted with TLS
- **Self-Signed Certificates**: Automatic certificate generation for each node
- **Secure Handshake**: Proper TLS handshake with authentication
- **Key Management**: RSA 2048-bit keys with SHA-256 signatures

### Architecture
- **Peer Discovery**: Central discovery server for finding peers
- **Direct P2P**: Messages sent directly between peers (not through server)
- **Connection Management**: Automatic connection handling and cleanup
- **Heartbeat System**: Keep-alive mechanism for peer presence

### User Experience
- **Username System**: Set and display usernames across the network
- **CLI Interface**: Clean command-line interface
- **Real-time Messaging**: Instant message delivery
- **Connection Status**: Visual feedback for peer connections

## 📋 Components

1. **generate_certificates.py**: TLS certificate generation
2. **discovery_server.py**: Central peer discovery and registration
3. **p2p_client.py**: P2P client with TLS encryption
4. **chat_ui.py**: Command-line user interface

## 🚀 Usage

### Step 1: Start Discovery Server

Run the discovery server first (in a separate terminal):

\`\`\`bash
python scripts/discovery_server.py
\`\`\`

The server will listen on `0.0.0.0:9000` by default.

### Step 2: Start Chat Clients

Run chat clients for each user (each in separate terminals):

\`\`\`bash
python scripts/chat_ui.py
\`\`\`

Follow the prompts:
- Enter a unique username
- Enter a listen port (e.g., 5001, 5002, etc.)
- Enter discovery server address (default: localhost:9000)

### Step 3: Connect and Chat

Available commands:
- `/list` - Discover available peers
- `/connect <username>` - Connect to a peer
- `/chat <username>` - Start chatting with a peer
- `/peers` - Show connected peers
- `/help` - Show help message
- `/quit` - Exit application

## 🔒 Security Features

### TLS Implementation
- **Protocol**: TLS 1.3 (with fallback to TLS 1.2)
- **Cipher Suites**: Strong encryption algorithms
- **Certificate Validation**: X.509 certificate validation
- **Key Exchange**: RSA key exchange

### Authentication
- **Peer Authentication**: Username-based identification
- **Certificate Validation**: Self-signed certificate verification
- **Connection Handshake**: Secure handshake protocol

### Data Protection
- **Encryption**: All messages encrypted in transit
- **Integrity**: Message integrity protection
- **Confidentiality**: End-to-end encryption between peers

## 🏗️ Architecture

\`\`\`
┌─────────────┐         ┌─────────────┐
│   Client A  │         │   Client B  │
│  (User: Alice)        │  (User: Bob)│
└──────┬──────┘         └──────┬──────┘
       │                       │
       │   1. Register         │
       ├──────────┐   ┌────────┤
       │          ▼   ▼        │
       │   ┌──────────────┐    │
       │   │  Discovery   │    │
       │   │    Server    │    │
       │   └──────────────┘    │
       │          │             │
       │   2. Discover Peers    │
       │◄─────────┴────────────►│
       │                        │
       │   3. Direct TLS        │
       │      Connection        │
       │◄──────────────────────►│
       │                        │
       │   4. Encrypted         │
       │      Messages          │
       │◄──────────────────────►│
\`\`\`

## 🛡️ Security Considerations

### Implemented
✅ TLS encryption for all P2P communications
✅ Certificate-based authentication
✅ Secure key generation and management
✅ Connection timeout and cleanup
✅ Input validation and error handling
✅ Peer identity verification

### Production Recommendations
- Use CA-signed certificates instead of self-signed
- Implement certificate pinning
- Add rate limiting for DoS protection
- Implement message signing for non-repudiation
- Add user authentication (password/token)
- Enable certificate revocation checking
- Use secure key storage (HSM/TPM)

## 🧪 Testing

### Test Scenario 1: Two Peers
1. Start discovery server
2. Start Client A (Alice on port 5001)
3. Start Client B (Bob on port 5002)
4. Alice: `/list` to see Bob
5. Alice: `/connect Bob`
6. Alice: `/chat Bob`
7. Alice types: "Hello Bob!"
8. Bob receives encrypted message

### Test Scenario 2: Multiple Peers
1. Start discovery server
2. Start 3+ clients with different usernames/ports
3. Each client can discover and connect to others
4. Test message routing between all peers

## 📦 Dependencies

- **cryptography**: For TLS certificates and encryption
- **Python 3.7+**: Required for SSL/TLS support

Install with:
\`\`\`bash
pip install cryptography
\`\`\`

## 🔧 Configuration

### Discovery Server
- **Host**: `0.0.0.0` (all interfaces)
- **Port**: `9000`
- **Peer Timeout**: 60 seconds
- **Cleanup Interval**: 30 seconds

### P2P Client
- **TLS Protocol**: TLS 1.2/1.3
- **Key Size**: 2048 bits
- **Certificate Validity**: 365 days
- **Heartbeat Interval**: 20 seconds

## 🐛 Troubleshooting

### Connection Refused
- Ensure discovery server is running
- Check firewall settings
- Verify port numbers are not in use

### TLS Handshake Failed
- Regenerate certificates
- Check certificate paths
- Verify TLS protocol support

### Peer Not Found
- Wait for heartbeat update (~20 seconds)
- Restart discovery server
- Check network connectivity

## 📄 License

This is a demonstration project for educational purposes.
