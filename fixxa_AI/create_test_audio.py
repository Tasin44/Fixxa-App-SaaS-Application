"""
Generate Test Audio File
========================
Creates a test audio file using text-to-speech for testing voice processing.

Run: python create_test_audio.py
"""

from pathlib import Path

def create_test_audio():
    """Create a test audio file using gTTS (Google Text-to-Speech)"""
    
    print("\n" + "="*60)
    print("  Creating Test Audio File")
    print("="*60 + "\n")
    
    # Test data
    test_text = """
    New client information.
    Client name is John Doe.
    Phone number is 555-123-4567.
    Address is 123 Main Street, New York.
    Email is john.doe@email.com.
    Service type is plumbing repair.
    Issue description: leaking pipe in the kitchen.
    Estimated cost is 150 dollars.
    Schedule appointment for tomorrow.
    Additional notes: urgent repair needed.
    """
    
    print("📝 Test text:")
    print(test_text)
    print("\n" + "-"*60 + "\n")
    
    try:
        from gtts import gTTS
        
        # Create audio
        tts = gTTS(text=test_text, lang='en', slow=False)
        
        # Save to file
        output_file = Path("test_client_audio.mp3")
        tts.save(str(output_file))
        
        print(f"✅ Audio file created: {output_file}")
        print(f"📁 Location: {output_file.absolute()}")
        print(f"\n🎵 Now use this file in Postman:")
        print(f"   1. Go to 'Upload and Process Audio File' request")
        print(f"   2. Body → form-data → audio (File)")
        print(f"   3. Select: {output_file.name}")
        print(f"   4. Click Send")
        print("\n" + "="*60 + "\n")
        
        return str(output_file)
        
    except ImportError:
        print("❌ gTTS not installed")
        print("\nInstall it:")
        print("   pip install gtts")
        print("\nThen run this script again.")
        return None


if __name__ == "__main__":
    create_test_audio()
