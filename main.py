import streamlit as st
import asyncio
import edge_tts
import io
import xml.etree.ElementTree as ET

# -------------------- Language Voice Config --------------------
LANGUAGE_VOICES = {
    'en': ['en-US-JennyNeural'],
    'ar': ['ar-SA-HamedNeural'],
    
}

# -------------------- Unicode-based Quick Language Segmenter --------------------
def detect_language_segments(text):
    segments = []
    current_segment, current_lang = "", "en"
    for char in text:
        # Arabic Unicode
        if '\u0600' <= char <= '\u06FF' or '\u0750' <= char <= '\u077F':
            new_lang = 'ar'
        # English/Latin
        elif '\u0000' <= char <= '\u007F':
            new_lang = 'en'
        else:
            new_lang = 'en'
        if new_lang != current_lang:
            if current_segment.strip():
                segments.append((current_segment.strip(), current_lang))
            current_segment, current_lang = char, new_lang
        else:
            current_segment += char
    if current_segment.strip():
        segments.append((current_segment.strip(), current_lang))
    return segments

# -------------------- Extract Only Human-Visible Text from SSML/XML --------------------
def extract_text_from_ssml(ssml):
    try:
        root = ET.fromstring(ssml)
        texts = []
        def recurse(element):
            if element.text and element.text.strip():
                texts.append(element.text.strip())
            for child in element:
                recurse(child)
                if child.tail and child.tail.strip():
                    texts.append(child.tail.strip())
        recurse(root)
        # Join with single space so it sounds like a logical paragraph
        return ' '.join(texts)
    except Exception as e:
        st.error(f"XML parsing error: {e}")
        return ssml

# -------------------- Async Plain Text Synthesis by Detected Lang --------------------
async def synthesize_tts_plain(text):
    segments = detect_language_segments(text)
    output = io.BytesIO()
    for segment, lang in segments:
        # Try the preferred voices for each lang, fallback to English if needed
        voices = LANGUAGE_VOICES.get(lang, LANGUAGE_VOICES['en'])
        success = False
        for voice in voices:
            try:
                communicate = edge_tts.Communicate(text=segment, voice=voice)
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        output.write(chunk["data"])
                success = True
                break
            except Exception as e:
                continue
        if not success:
            st.warning(f"Could not synthesize for language '{lang}' (chunk: {segment}).")
    return output.getvalue() if output.getvalue() else None

# -------------------- Async True SSML Synthesis --------------------
async def synthesize_tts_ssml(ssml):
    try:
        ET.fromstring(ssml)  # XML validation
    except ET.ParseError as e:
        st.error(f"SSML XML Error: {e}")
        return None
    communicate = edge_tts.Communicate(text=ssml, voice="en-US-JennyNeural")
    output = io.BytesIO()
    got_audio = False
    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                output.write(chunk["data"])
                got_audio = True
    except Exception as e:
        st.error(f"Edge TTS error: {str(e)}")
        return None
    if not got_audio:
        st.error("No audio produced. Check that <voice> names and language codes in your SSML are supported by Edge/Azure.")
        return None
    return output.getvalue()

# -------------------- UI --------------------
st.set_page_config(page_title="Edge SSML/Multilingual TTS Demo")
st.title("🗣️ Multilingual/SSML TTS (Edge)")

col1, col2 = st.columns(2)
with col1:
    is_ssml = st.checkbox("Input is SSML/XML", value=True)
with col2:
    flatten_ssml = st.checkbox("Extract and speak only human text from SSML (ignore tags/voices)", value=False)

default_text = """<?xml version='1.0' encoding='UTF-8'?>
<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='ar-SA'>
<prosody rate="medium" pitch="default">
  <voice name='en-US-JennyNeural'>
    <lang xml:lang='en-US'>
      Multilingual test number <say-as interpret-as="cardinal">2</say-as> -
    </lang>
  </voice>
  <break time="500ms"/>
  <voice name='ar-SA-HamedNeural'>
    <lang xml:lang='ar-SA'>
      اختبار رقم <say-as interpret-as="cardinal">2</say-as> -
      هذه جملة عربية للاختبار.
    </lang>
  </voice>
  <break time="500ms"/>
  <voice name='en-US-JennyNeural'>
    <lang xml:lang='en-US'>
      Test Nummer <say-as interpret-as="cardinal">2</say-as>
    </lang>
  </voice>
</prosody>
</speak>""" if is_ssml else "Multilingual test number 2 - اختبار رقم 2 - Test Nummer 2"
user_input = st.text_area("Enter SSML or plain text:", value=default_text, height=350)

if st.button("🎵 Synthesize Speech"):
    with st.spinner("Synthesizing..."):
        if is_ssml and not flatten_ssml:
            audio = asyncio.run(synthesize_tts_ssml(user_input))
        else:
            if is_ssml:
                extracted = extract_text_from_ssml(user_input)
                st.info(f"Extracted text to be spoken: {extracted}")
                audio = asyncio.run(synthesize_tts_plain(extracted))
            else:
                audio = asyncio.run(synthesize_tts_plain(user_input))

        if audio:
            st.audio(audio, format="audio/mp3")
            st.download_button("Download MP3", data=audio, file_name="speech.mp3", mime="audio/mp3")
        else:
            st.error("TTS failed. For SSML: check that your XML, <voice> names, and language codes are supported by Edge/Azure.")

st.markdown("---")
st.info(
    """
    **SSML input**:  
    - Leave "Extract and speak..." OFF to use all SSML features: voices, tags, breaks, say-as (true rich SSML synthesis).  
    - Turn it ON to only extract and speak visible text as plain, with automatic language detection and switching for Arabic/English/Latin chunks.
    """
)
