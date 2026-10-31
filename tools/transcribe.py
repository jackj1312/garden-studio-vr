"""Transcribe one voice note from the headset (called by tools/https-serve.py after a /marks/audio upload).
    python tools/transcribe.py <audio file>      -> prints the text
Runs locally on the Mac with faster-whisper (no audio leaves the machine). Model: base.en, CPU, int8."""
import sys, os
os.environ.setdefault("HF_HUB_OFFLINE", "0")
try:
    from faster_whisper import WhisperModel
except ImportError:
    print("", end=""); sys.exit(0)              # not installed yet: the note stays "awaiting transcription"
import subprocess, numpy as np, imageio_ffmpeg
# decode with ffmpeg to 16 kHz mono floats (the bundled PyAV decoder clashes with this faster-whisper version)
raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-loglevel", "error", "-i", sys.argv[1],
                      "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
audio = np.frombuffer(raw, np.float32)
model = WhisperModel("base.en", device="cpu", compute_type="int8")
segs, _ = model.transcribe(audio, beam_size=1, vad_filter=False)
print(" ".join(s.text.strip() for s in segs).strip())
