"""
Audio Testing Module - Test microphone and speakers
Run this first to verify audio works on your system
"""
import pyaudio
import wave
import sys

class AudioTester:
    def __init__(self):
        self.CHUNK = 1024  # Audio frames per buffer
        self.FORMAT = pyaudio.paInt16  # 16-bit audio
        self.CHANNELS = 1  # Mono audio
        self.RATE = 44100  # Sample rate (Hz)
        
        self.audio = pyaudio.PyAudio()
    
    def list_devices(self):
        """List all audio input/output devices"""
        print("\n" + "="*60)
        print("AVAILABLE AUDIO DEVICES")
        print("="*60)
        
        info = self.audio.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        
        for i in range(0, numdevices):
            device_info = self.audio.get_device_info_by_host_api_device_index(0, i)
            
            # Check if device supports input
            if device_info.get('maxInputChannels') > 0:
                print(f"\n[INPUT {i}] {device_info.get('name')}")
                print(f"  Channels: {device_info.get('maxInputChannels')}")
                print(f"  Sample Rate: {device_info.get('defaultSampleRate')}")
            
            # Check if device supports output
            if device_info.get('maxOutputChannels') > 0:
                print(f"\n[OUTPUT {i}] {device_info.get('name')}")
                print(f"  Channels: {device_info.get('maxOutputChannels')}")
                print(f"  Sample Rate: {device_info.get('defaultSampleRate')}")
        
        print("\n" + "="*60)
    
    def test_microphone(self, duration=3):
        """Test microphone by recording and playing back"""
        print(f"\n🎤 Testing Microphone - Recording for {duration} seconds...")
        print("Speak into your microphone now!")
        
        stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )
        
        frames = []
        
        for i in range(0, int(self.RATE / self.CHUNK * duration)):
            data = stream.read(self.CHUNK)
            frames.append(data)
            
            # Simple volume indicator
            if i % 10 == 0:
                sys.stdout.write('.')
                sys.stdout.flush()
        
        print("\n✓ Recording complete!")
        
        stream.stop_stream()
        stream.close()
        
        # Play back what was recorded
        print("\n🔊 Playing back your recording...")
        
        stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            output=True
        )
        
        for frame in frames:
            stream.write(frame)
        
        stream.stop_stream()
        stream.close()
        
        print("✓ Playback complete!\n")
    
    def test_echo(self, duration=10):
        """Real-time echo test - hear yourself with slight delay"""
        print(f"\n🔄 Echo Test - You should hear yourself speaking")
        print(f"Running for {duration} seconds... Press Ctrl+C to stop early")
        
        input_stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )
        
        output_stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            output=True,
            frames_per_buffer=self.CHUNK
        )
        
        print("Speak now - you should hear yourself!")
        
        try:
            for i in range(0, int(self.RATE / self.CHUNK * duration)):
                data = input_stream.read(self.CHUNK)
                output_stream.write(data)
                
                if i % 20 == 0:
                    sys.stdout.write('.')
                    sys.stdout.flush()
        except KeyboardInterrupt:
            print("\n\nStopped by user")
        
        print("\n✓ Echo test complete!")
        
        input_stream.stop_stream()
        input_stream.close()
        output_stream.stop_stream()
        output_stream.close()
    
    def cleanup(self):
        """Clean up PyAudio"""
        self.audio.terminate()

def main():
    print("="*60)
    print("DARTCHAT - AUDIO SYSTEM TEST")
    print("="*60)
    
    tester = AudioTester()
    
    try:
        while True:
            print("\n📋 Audio Test Menu:")
            print("1. List all audio devices")
            print("2. Test microphone (record & playback)")
            print("3. Echo test (hear yourself in real-time)")
            print("4. Exit")
            
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == '1':
                tester.list_devices()
            
            elif choice == '2':
                duration = input("Recording duration in seconds [3]: ").strip()
                duration = int(duration) if duration else 3
                tester.test_microphone(duration)
            
            elif choice == '3':
                duration = input("Echo test duration in seconds [10]: ").strip()
                duration = int(duration) if duration else 10
                tester.test_echo(duration)
            
            elif choice == '4':
                print("\n✓ Exiting...")
                break
            
            else:
                print("❌ Invalid option!")
    
    except KeyboardInterrupt:
        print("\n\n✓ Interrupted by user")
    
    finally:
        tester.cleanup()
        print("✓ Cleanup complete")

if __name__ == "__main__":
    main()