import streamlit as st
import asyncio
import edge_tts
import io
import xml.etree.ElementTree as ET
import re

# --- Configuration ---
# Primary multilingual voices to try
MULTILINGUAL_VOICES = [
    "en-US-JennyMultilingualNeural",
    "en-US-AriaMultilingualNeural",
    "de-DE-SeraphinaMultilingualNeural",
    "es-ES-XimenaMultilingualNeural",
    "fr-FR-VivienneMultilingualNeural",
    "zh-CN-XiaoxiaoMultilingualNeural"
]

# Language-specific voices as fallback
LANGUAGE_VOICES = {
    'en': ['en-US-JennyNeural', 'en-US-AriaNeural', 'en-GB-SoniaNeural'],
    'ar': ['ar-SA-ZariyahNeural', 'ar-EG-SalmaNeural', 'ar-AE-FatimaNeural'],
    'te': ['te-IN-ShrutiNeural', 'te-IN-MohanNeural'],
    'ml': ['ml-IN-SobhanaNeural', 'ml-IN-MidhunNeural'],
    'zh': ['zh-CN-XiaoxiaoNeural', 'zh-CN-YunyangNeural', 'zh-TW-HsiaoChenNeural'],
    'hi': ['hi-IN-SwaraNeural', 'hi-IN-MadhurNeural'],
    'es': ['es-ES-ElviraNeural', 'es-MX-DaliaNeural'],
    'fr': ['fr-FR-DeniseNeural', 'fr-CA-SylvieNeural'],
    'de': ['de-DE-KatjaNeural', 'de-AT-IngridNeural'],
    'ja': ['ja-JP-NanamiNeural', 'ja-JP-KeitaNeural'],
    'ko': ['ko-KR-SunHiNeural', 'ko-KR-InJoonNeural'],
    'ru': ['ru-RU-SvetlanaNeural', 'ru-RU-DmitryNeural'],
    'it': ['it-IT-ElsaNeural', 'it-IT-DiegoNeural'],
    'pt': ['pt-BR-FranciscaNeural', 'pt-PT-RaquelNeural'],
    'ta': ['ta-IN-PallaviNeural', 'ta-IN-ValluvarNeural'],
    'ur': ['ur-PK-UzmaNeural', 'ur-IN-GulNeural'],
    'bn': ['bn-IN-TanishaaNeural', 'bn-BD-NabanitaNeural'],
    'gu': ['gu-IN-DhwaniNeural', 'gu-IN-NiranjanNeural'],
    'kn': ['kn-IN-SapnaNeural', 'kn-IN-GaganNeural'],
    'mr': ['mr-IN-AarohiNeural', 'mr-IN-ManoharNeural'],
    'pa': ['pa-IN-PavanNeural', 'pa-IN-PrabhjotNeural'],
    'tr': ['tr-TR-EmelNeural', 'tr-TR-AhmetNeural'],
    'nl': ['nl-NL-ColetteNeural', 'nl-BE-ArnaudNeural'],
    'pl': ['pl-PL-ZofiaNeural', 'pl-PL-MarekNeural'],
    'sv': ['sv-SE-SofieNeural', 'sv-SE-MattiasNeural'],
    'da': ['da-DK-ChristelNeural', 'da-DK-JeppeNeural'],
    'no': ['no-NO-PernilleNeural', 'no-NO-FinnNeural'],
    'fi': ['fi-FI-NooraNeural', 'fi-FI-HarriNeural'],
    'th': ['th-TH-PremwadeeNeural', 'th-TH-NiwatNeural'],
    'vi': ['vi-VN-HoaiMyNeural', 'vi-VN-NamMinhNeural'],
    'id': ['id-ID-GadisNeural', 'id-ID-ArdiNeural'],
    'ms': ['ms-MY-YasminNeural', 'ms-MY-OsmanNeural'],
    'tl': ['fil-PH-AngeloNeural', 'fil-PH-BlessicaNeural']
}

# --- Language Detection Function ---
def detect_language_segments(text):
    """
    Simple language detection based on character patterns.
    Returns segments with detected languages.
    """
    segments = []
    current_segment = ""
    current_lang = 'en'
    
    for char in text:
        if '\u0600' <= char <= '\u06FF':  # Arabic
            if current_lang != 'ar':
                if current_segment.strip():
                    segments.append((current_segment.strip(), current_lang))
                current_segment = char
                current_lang = 'ar'
            else:
                current_segment += char
        elif '\u0C00' <= char <= '\u0C7F':  # Telugu
            if current_lang != 'te':
                if current_segment.strip():
                    segments.append((current_segment.strip(), current_lang))
                current_segment = char
                current_lang = 'te'
            else:
                current_segment += char
        elif '\u0D00' <= char <= '\u0D7F':  # Malayalam
            if current_lang != 'ml':
                if current_segment.strip():
                    segments.append((current_segment.strip(), current_lang))
                current_segment = char
                current_lang = 'ml'
            else:
                current_segment += char
        elif '\u4E00' <= char <= '\u9FFF':  # Chinese
            if current_lang != 'zh':
                if current_segment.strip():
                    segments.append((current_segment.strip(), current_lang))
                current_segment = char
                current_lang = 'zh'
            else:
                current_segment += char
        elif '\u0900' <= char <= '\u097F':  # Hindi/Devanagari
            if current_lang != 'hi':
                if current_segment.strip():
                    segments.append((current_segment.strip(), current_lang))
                current_segment = char
                current_lang = 'hi'
            else:
                current_segment += char
        elif '\u0B80' <= char <= '\u0BFF':  # Tamil
            if current_lang != 'ta':
                if current_segment.strip():
                    segments.append((current_segment.strip(), current_lang))
                current_segment = char
                current_lang = 'ta'
            else:
                current_segment += char
        else:  # Default to English
            if current_lang != 'en':
                if current_segment.strip():
                    segments.append((current_segment.strip(), current_lang))
                current_segment = char
                current_lang = 'en'
            else:
                current_segment += char
    
    if current_segment.strip():
        segments.append((current_segment.strip(), current_lang))
    
    return segments

# --- Voice Testing Function ---
async def test_voice(voice_name, test_text="Hello"):
    """Test if a voice is working"""
    try:
        communicate = edge_tts.Communicate(text=test_text, voice=voice_name)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                return True
        return False
    except:
        return False

# --- Find Working Voice ---
async def find_working_voice():
    """Find a working multilingual voice"""
    st.info("🔍 Testing voices...")
    
    # Try multilingual voices first
    for voice in MULTILINGUAL_VOICES:
        if await test_voice(voice):
            st.success(f"✅ Found working multilingual voice: {voice}")
            return voice, 'multilingual'
    
    # If no multilingual voice works, we'll use language-specific approach
    st.warning("⚠️ No multilingual voice available. Will use language-specific voices.")
    return None, 'language-specific'

# --- Synthesize with Language-Specific Voices ---
async def synthesize_with_language_voices(text_segments):
    """Synthesize each language segment with appropriate voice"""
    audio_parts = []
    
    for text, lang in text_segments:
        if lang not in LANGUAGE_VOICES:
            lang = 'en'  # Fallback to English
        
        # Try voices for this language
        working_voice = None
        for voice in LANGUAGE_VOICES[lang]:
            if await test_voice(voice, text[:50]):  # Test with first 50 chars
                working_voice = voice
                break
        
        if not working_voice:
            # Fallback to English if no voice works for this language
            working_voice = 'en-US-JennyNeural'
        
        # Synthesize this segment
        try:
            communicate = edge_tts.Communicate(text=text, voice=working_voice)
            segment_audio = io.BytesIO()
            
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    segment_audio.write(chunk["data"])
            
            if segment_audio.getvalue():
                audio_parts.append(segment_audio.getvalue())
                st.write(f"🎵 {lang.upper()}: \"{text[:50]}...\" → {working_voice}")
        
        except Exception as e:
            st.error(f"Error synthesizing {lang}: {e}")
    
    return audio_parts

# --- Main Synthesis Function ---
async def synthesize_speech(text):
    """
    Main synthesis function that handles multilingual text dynamically
    """
    # First, try to find a working multilingual voice
    voice, voice_type = await find_working_voice()
    
    if voice_type == 'multilingual' and voice:
        # Use multilingual voice with original text
        try:
            communicate = edge_tts.Communicate(text=text, voice=voice)
            audio_bytes_io = io.BytesIO()
            
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes_io.write(chunk["data"])
            
            if audio_bytes_io.getvalue():
                return audio_bytes_io.getvalue(), voice, 'multilingual'
        
        except Exception as e:
            st.error(f"Error with multilingual voice: {e}")
    
    # Fallback: Use language-specific voices
    st.info("🔄 Using language-specific synthesis...")
    segments = detect_language_segments(text)
    
    if not segments:
        segments = [(text, 'en')]  # Default to English if no segments detected
    
    st.write("📝 Detected language segments:")
    for i, (segment_text, lang) in enumerate(segments, 1):
        st.write(f"{i}. **{lang.upper()}**: {segment_text}")
    
    audio_parts = await synthesize_with_language_voices(segments)
    
    if audio_parts:
        # Combine all audio parts
        combined_audio = b''.join(audio_parts)
        return combined_audio, 'mixed-voices', 'language-specific'
    
    return None, None, None

# --- Streamlit UI ---
st.set_page_config(
    page_title="Multilingual TTS App",
    page_icon="🗣️",
    layout="centered"
)

st.title("🗣️ Advanced Multilingual Text-to-Speech")
st.markdown(
    """
    Enter text in **any language** below! This app will automatically detect languages
    and use the best available voices for synthesis.
    
    **Supported Languages**: English, Arabic, Telugu, Malayalam, Chinese, Hindi, Tamil, 
    Spanish, French, German, Japanese, Korean, Russian, Italian, Portuguese, Turkish, 
    Dutch, Polish, Swedish, Danish, Norwegian, Finnish, Thai, Vietnamese, Indonesian, 
    Malay, Filipino, Urdu, Bengali, Gujarati, Kannada, Marathi, Punjabi, and more!
    """
)

# Text input area for user
user_input_text = st.text_area(
    "Enter your multilingual text here:",
    "Hello! السلام عليكم. ఎలా ఉన్నావు? ഞാൻ സুഖമാണ്. This is a test. 谢谢！ नमस्ते! ¡Hola! Bonjour! こんにちは！",
    height=150
)

# Synthesize button
if st.button("🎵 Synthesize Speech"):
    if not user_input_text.strip():
        st.warning("Please enter some text to synthesize.")
    else:
        with st.spinner("Synthesizing speech..."):
            try:
                result = asyncio.run(synthesize_speech(user_input_text))
                
                if result[0] is not None:
                    audio_data, voice_info, synthesis_type = result
                    
                    st.subheader("🎧 Play Audio:")
                    st.audio(audio_data, format="audio/mp3", start_time=0)

                    st.subheader("📥 Download Audio:")
                    st.download_button(
                        label="Download MP3",
                        data=audio_data,
                        file_name="multilingual_speech.mp3",
                        mime="audio/mp3"
                    )
                    
                    if synthesis_type == 'multilingual':
                        st.success(f"✅ Speech synthesized successfully using multilingual voice: {voice_info}")
                    else:
                        st.success(f"✅ Speech synthesized successfully using language-specific voices!")
                    
                else:
                    st.error("❌ Failed to synthesize speech. Please try again.")

            except Exception as e:
                st.error(f"An error occurred during synthesis: {e}")

st.markdown("---")
st.info(
    """
    **How it works:**
    1. 🔍 **Voice Detection**: Tries to find working multilingual voices first
    2. 🌐 **Language Detection**: Automatically detects different languages in your text
    3. 🎵 **Smart Synthesis**: Uses the best available voice for each language
    4. 🔄 **Fallback System**: Falls back to language-specific voices if needed
    
    **Note**: Requires internet connection for Microsoft Edge TTS service.
    """
)