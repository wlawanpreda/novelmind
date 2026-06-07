import sys
import os
import argparse
from pathlib import Path

# Try to import OCR requirements
try:
    import objc
    from Foundation import NSURL
    from Vision import (
        VNImageRequestHandler,
        VNRecognizeTextRequest,
        VNRequestTextRecognitionLevelAccurate,
    )
except ImportError:
    print("Error: Missing required libraries for OCR. Please install 'pyobjc':")
    print("pip install pyobjc-core pyobjc-framework-Vision pyobjc-framework-Cocoa")
    sys.exit(1)

# Try to import TTS requirements
try:
    import pyttsx3
except ImportError:
    print("Warning: 'pyttsx3' is not installed. Text-to-Speech will be disabled.")
    pyttsx3 = None

def perform_ocr(image_path: str, languages: list = None) -> str:
    """
    Performs OCR on the specified image file using Apple's Vision framework.
    """
    if not os.path.exists(image_path):
        return f"Error: File not found at {image_path}"

    if not languages:
        languages = ["th-TH", "en-US"]

    image_url = NSURL.fileURLWithPath_(str(Path(image_path).resolve()))

    request = VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(languages)
    request.setUsesLanguageCorrection_(True)

    handler = VNImageRequestHandler.alloc().initWithURL_options_(image_url, None)
    success, error = handler.performRequests_error_([request], None)

    if not success:
        return f"Error performing OCR request: {error}"

    results = request.results()
    if not results:
        return ""

    extracted_lines = []
    for observation in results:
        candidates = observation.topCandidates_(1)
        if candidates:
            text = candidates[0].string()
            extracted_lines.append(text)

    return "\n".join(extracted_lines)

def speak_text(text: str):
    """
    Reads the text aloud using the local pyttsx3 TTS model.
    """
    if not pyttsx3:
        print("[TTS Disabled] Install pyttsx3 to enable voice.")
        return

    print("\n🗣️ Reading out loud using local TTS...")
    engine = pyttsx3.init()
    
    # Configure speed (slower is more readable)
    engine.setProperty('rate', 150)
    
    # Configure voice to support Thai if available, otherwise default
    voices = engine.getProperty('voices')
    
    # Simple search for a Thai voice in the macOS speech engine
    thai_voice = None
    for voice in voices:
        # Many Thai voices on macOS contain 'th' or 'thai' in their identifier/languages
        if any('th' in str(lang).lower() for lang in voice.languages) or 'thai' in voice.name.lower():
            thai_voice = voice.id
            break
            
    if thai_voice:
        engine.setProperty('voice', thai_voice)
        print(f"Using Thai Voice: {thai_voice}")
    else:
        print("Using Default Voice (Thai voice might not be downloaded in System Settings).")

    engine.say(text)
    engine.runAndWait()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apple Vision OCR & Local TTS (macOS)")
    parser.add_argument("image_path", help="Path to the image file (png, jpg, jpeg, etc.)")
    parser.add_argument("--langs", nargs="+", default=["th-TH", "en-US"], 
                        help="Language codes for OCR (e.g., th-TH en-US)")
    parser.add_argument("--silent", action="store_true", help="Disable text-to-speech")
    
    args = parser.parse_args()
    
    print(f"🔍 Analyzing {args.image_path} with Apple Vision OCR...")
    ocr_result = perform_ocr(args.image_path, args.langs)
    
    if ocr_result:
        print("\n📝 Extracted Text:")
        print("-" * 40)
        print(ocr_result)
        print("-" * 40)
        
        if not args.silent:
            speak_text(ocr_result)
    else:
        print("No text detected in the image.")
