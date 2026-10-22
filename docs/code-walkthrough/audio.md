# Walkthrough: `careercrew/audio.py`

**File purpose:** Thin OpenAI STT/TTS wrappers for the mock interviewer. **Never raises** into the UI — returns `""` / `None` so the interview becomes text-only.

---

## `audio_available()`

True when `settings.has_audio` (OpenAI key present).

## `_client()`

Build `OpenAI` client with key + optional base URL.

---

## `transcribe(audio_path)`

**What:** If path missing / no key → `""`. Else `whisper-1` (`settings.stt_model`) on file bytes → return text. On any error → log + `""`.  
**I/O:** Read audio file; HTTPS to OpenAI.  
**Say this:** “STT failure never kills the interview — type the answer instead.”

---

## `speak(text)`

**What:** Empty/no key → `None`. Else `tts-1` + voice → write temp `.mp3` → return path. On error → `None`.  
**I/O:** Temp file; OpenAI speech API.  
**Say this:** “TTS speaks the question; if it fails, the question still shows as text.”

---

## How it connects

Called from `callbacks_interview._ask_question` (speak) and `callbacks_interview.interview_submit` (transcribe).
