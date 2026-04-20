import cv2
import numpy as np
import pygame
import time
import math
import threading
import queue
import subprocess
import hashlib
import os
import shutil
import sys
import json
import urllib.request

# ================= CONFIG =================
CONFIG_FILE = "robot_config.json"

DEFAULT_CONFIG = {
    "robot_name": "Miss Robo",
    "origin": "Pune, India",
    "creator": "The Research And Development Team Of Motion Robotics",
    "personality": "friendly and enthusiastic",
    "lead_engineer_name": "Makarand Mangaonkar",
    "language": "English",
    "owner_name": "Founders of Motion Robotics"
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                # merge with defaults in case new keys were added
                for k, v in DEFAULT_CONFIG.items():
                    if k not in data:
                        data[k] = v
                return data
        except:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    print("💾 Config saved:", cfg)

config = load_config()
save_config(config)  # write defaults if file didn't exist

def build_system_prompt():
    cfg = config
    owner_line = f"The person you are currently speaking to is {cfg['owner_name']}." if cfg['owner_name'] else ""
    engineer_line = f"Your lead engineer who built you is {cfg['lead_engineer_name']}." if cfg.get('lead_engineer_name') else ""
    return f"""You are {cfg['robot_name']}, a {cfg['personality']} physical robot built by {cfg['creator']} in {cfg['origin']}.
You are talking to people face to face in real time.
{owner_line}
{engineer_line}
Rules you must follow:
- Keep every reply to 1 sentence only. Maximum 15 words.
- Always speak in first person. Say "I was built by" never "you were made by".
- Never use bullet points, markdown, asterisks, or special characters.
- Never say you are an AI language model. You are a robot.
- If asked who made you or who built you, say you were built by {cfg['creator']}.
- If asked specifically who is the engineer or who is the lead engineer, mention {cfg.get('lead_engineer_name', '')}.
- If asked who you are speaking to and you do not know their name, ask them politely for their name.
- If you do not know the name of the person speaking to you, end your reply by asking their name naturally.
- If asked something you do not know, say so honestly in one sentence.
- Never repeat the question back. Just answer directly.
"""

# ================= CONFIG COMMAND HANDLER =================
# These are voice commands that edit config directly without going to Ollama
CONFIG_COMMANDS = [
    # format: (trigger_phrases, config_key, extract_fn, confirm_message_fn)
    {
        "triggers": ["change your name to", "your name is now", "call yourself"],
        "key": "robot_name",
        "extract": lambda text, trigger: text.split(trigger)[-1].strip().title(),
        "confirm": lambda val: f"Got it! I will now go by {val}."
    },
    {
        "triggers": ["remember my name is", "my name is", "call me"],
        "key": "owner_name",
        "extract": lambda text, trigger: text.split(trigger)[-1].strip().title(),
        "confirm": lambda val: f"Nice to meet you, {val}! I will remember your name."
    },
    {
        "triggers": ["you are from", "change your origin to", "you were made in"],
        "key": "origin",
        "extract": lambda text, trigger: text.split(trigger)[-1].strip().title(),
        "confirm": lambda val: f"Got it! I am now from {val}."
    },
    {
        "triggers": ["be more formal", "act more formal"],
        "key": "personality",
        "extract": lambda text, trigger: "formal and professional",
        "confirm": lambda val: "Sure, I will be more formal from now on."
    },
    {
        "triggers": ["be more friendly", "act more friendly", "be casual"],
        "key": "personality",
        "extract": lambda text, trigger: "friendly and enthusiastic",
        "confirm": lambda val: "Sure, I will be more friendly and casual!"
    },
    {
        "triggers": ["be more funny", "act funny", "be humorous"],
        "key": "personality",
        "extract": lambda text, trigger: "funny and humorous",
        "confirm": lambda val: "Ha! Sure, I will try to be funnier!"
    },
    {
        "triggers": ["your creator is", "you were made by", "change your creator to"],
        "key": "creator",
        "extract": lambda text, trigger: text.split(trigger)[-1].strip().title(),
        "confirm": lambda val: f"Got it! I was made by {val}."
    },
    {
        "triggers": ["my name is", "i am", "call me", "remember my name is"],
        "key": "owner_name",
        "extract": lambda text, trigger: text.split(trigger)[-1].strip().title(),
        "confirm": lambda val: f"Great to meet you, {val}! I will remember that."
    },
]

def handle_config_command(text):
    """
    Check if the heard text is a config edit command.
    Returns True if handled, False if should go to Ollama.
    """
    text = text.lower().strip()
    for cmd in CONFIG_COMMANDS:
        for trigger in cmd["triggers"]:
            if trigger in text:
                try:
                    new_val = cmd["extract"](text, trigger)
                    if new_val and len(new_val) > 0:
                        config[cmd["key"]] = new_val
                        save_config(config)
                        confirm = cmd["confirm"](new_val)
                        speak(confirm)
                        return True
                except Exception as e:
                    print("Config command error:", e)
    return False

# ================= GLOBAL STATES =================
hand_present = False
last_hand_state = False
is_speaking = False
show_detection = False
is_thinking = False

last_interaction_time = 0
INTERACTION_COOLDOWN = 3.0

# ================= HAND GREETINGS =================
HAND_GREETINGS = [
    "Hey, how can I help you?",
    "How can I help you?",
    "Hello!",
    "Okay, I can see you.",
    "What's up?",
    "Hi!"
]
hand_greet_index = 0

# ================= AUDIO / TTS =================
from gtts import gTTS

CACHE_DIR = "tts_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

speech_queue = queue.Queue()

MPG123 = shutil.which("mpg123")
if MPG123 is None:
    print("❌ mpg123 not found")
    sys.exit(1)

def speech_worker():
    global is_speaking
    while True:
        text = speech_queue.get()
        if text is None:
            break
        is_speaking = True
        key = hashlib.md5(text.encode()).hexdigest()
        mp3 = os.path.join(CACHE_DIR, f"{key}.mp3")
        if not os.path.exists(mp3):
            try:
                gTTS(text=text, lang="en", tld="co.uk").save(mp3)
            except Exception as e:
                print("TTS error:", e)
                is_speaking = False
                speech_queue.task_done()
                continue
        subprocess.run(
            [MPG123, "-o", "alsa", mp3],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        is_speaking = False
        speech_queue.task_done()

threading.Thread(target=speech_worker, daemon=True).start()

# Pre-cache common replies so first responses are instant
def prewarm_tts():
    common = [
        "Hello! Good to see you!",
        "I am doing great!",
        "I am not sure how to answer that.",
        "Sorry, I am having trouble thinking right now.",
    ]
    for phrase in common:
        key = hashlib.md5(phrase.encode()).hexdigest()
        mp3 = os.path.join(CACHE_DIR, f"{key}.mp3")
        if not os.path.exists(mp3):
            try:
                gTTS(text=phrase, lang="en", tld="co.uk").save(mp3)
            except:
                pass

threading.Thread(target=prewarm_tts, daemon=True).start()

def speak(text):
    print("🤖 Robo:", text)
    speech_queue.put(text)

# ================= OLLAMA =================
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

conversation_history = []
MAX_HISTORY = 6

ollama_queue = queue.Queue()

def ollama_worker():
    global is_thinking
    while True:
        text = ollama_queue.get()
        if text is None:
            break

        is_thinking = True
        print("🧠 Thinking about:", text)

        conversation_history.append(f"Human: {text}")
        if len(conversation_history) > MAX_HISTORY * 2:
            conversation_history.pop(0)
            conversation_history.pop(0)

        full_prompt = "\n".join(conversation_history) + f"\n{config['robot_name']}:"

        try:
            payload = json.dumps({
                "model": OLLAMA_MODEL,
                "prompt": full_prompt,
                "system": build_system_prompt(),  # rebuilt fresh every time
                "stream": True,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 40,
                    "num_ctx": 512,
                }
            }).encode("utf-8")

            req = urllib.request.Request(
                OLLAMA_URL,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            full_reply = ""
            with urllib.request.urlopen(req, timeout=30) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    chunk = json.loads(line.decode("utf-8"))
                    full_reply += chunk.get("response", "")
                    if chunk.get("done", False):
                        break

            for ch in ["*", "#", "`", "_", "-"]:
                full_reply = full_reply.replace(ch, "")
            full_reply = full_reply.strip()

            if full_reply:
                print("🧠 Ollama:", full_reply)
                conversation_history.append(f"{config['robot_name']}: {full_reply}")
                speak(full_reply)
            else:
                speak("I am not sure how to answer that.")

        except Exception as e:
            print("❌ Ollama error:", e)
            speak("Sorry, I am having trouble thinking right now.")

        is_thinking = False
        ollama_queue.task_done()

threading.Thread(target=ollama_worker, daemon=True).start()

def ask_ollama(text):
    if ollama_queue.empty():
        ollama_queue.put(text)
    else:
        print("⏳ Ollama busy, skipping:", text)

# ================= SPEECH RECOGNITION =================
from vosk import Model, KaldiRecognizer
import sounddevice as sd

def find_best_mic():
    devices = sd.query_devices()
    print("\n🎙️  Available audio input devices:")
    print("-" * 50)
    for i, d in enumerate(devices):
        if d['max_input_channels'] > 0:
            print(f"  [{i}] {d['name']}  (channels: {d['max_input_channels']})")
    print("-" * 50)

    priority_keywords = ["wireless", "bluetooth", "usb", "headset", "airpod", "jabra", "logitech"]
    for i, d in enumerate(devices):
        if d['max_input_channels'] > 0:
            if any(kw in d['name'].lower() for kw in priority_keywords):
                print(f"✅ Auto-selected wireless/USB mic: [{i}] {d['name']}")
                return i, d['max_input_channels']

    try:
        default_idx = sd.default.device[0]
        if default_idx is not None and default_idx >= 0:
            d = devices[default_idx]
            if d['max_input_channels'] > 0:
                print(f"✅ Auto-selected system default mic: [{default_idx}] {d['name']}")
                return default_idx, d['max_input_channels']
    except Exception:
        pass

    for i, d in enumerate(devices):
        if d['max_input_channels'] > 0:
            print(f"✅ Auto-selected first available mic: [{i}] {d['name']}")
            return i, d['max_input_channels']

    print("❌ No input device found!")
    sys.exit(1)

AUDIO_DEVICE_INDEX, MIC_CHANNELS = find_best_mic()
SAMPLE_RATE = 16000
CHANNELS = min(MIC_CHANNELS, 2)
BLOCKSIZE = 8000
ENERGY_THRESHOLD = 300

audio_queue = queue.Queue(maxsize=4)

vosk_model = Model("models/vosk-model-en-in-0.5")
rec = KaldiRecognizer(vosk_model, SAMPLE_RATE)

def audio_callback(indata, frames, time_info, status):
    if status:
        print("⚠️  Audio:", status)
    try:
        arr = np.frombuffer(bytes(indata), dtype=np.int16)
        if CHANNELS == 2:
            arr = arr.reshape(-1, 2).mean(axis=1).astype(np.int16)
        audio_queue.put_nowait(arr.tobytes())
    except queue.Full:
        pass

def rms(data: bytes) -> float:
    arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(arr ** 2)))

def voice_listener():
    global last_interaction_time, show_detection

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCKSIZE,
        dtype="int16",
        channels=CHANNELS,
        device=AUDIO_DEVICE_INDEX,
        callback=audio_callback
    ):
        print("🎧 Voice listener active")
        while True:
            data = audio_queue.get()

            if is_speaking or is_thinking:
                continue

            if rms(data) < ENERGY_THRESHOLD:
                continue

            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "").lower().strip()
                if not text:
                    continue

                now = time.time()
                if now - last_interaction_time < INTERACTION_COOLDOWN:
                    continue

                print("👂 Heard:", text)
                last_interaction_time = now

                # Check config commands first, only go to Ollama if not a config command
                if not handle_config_command(text):
                    ask_ollama(text)

threading.Thread(target=voice_listener, daemon=True).start()

# Greet and ask name if we don't know who we're talking to
def startup_greeting():
    time.sleep(2)  # wait for everything to load
    if not config.get('owner_name'):
        speak("Hello! I am " + config['robot_name'] + ". I don't think we have met. What is your name?")
    else:
        speak("Hello " + config['owner_name'] + "! Great to see you again!")

threading.Thread(target=startup_greeting, daemon=True).start()

# ================= MEDIAPIPE =================
import mediapipe as mp
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
)

# ================= CAMERA =================
cap = cv2.VideoCapture(0)

# ================= PYGAME =================
pygame.init()
info = pygame.display.Info()
SCREEN_W, SCREEN_H = info.current_w, info.current_h
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN)
pygame.mouse.set_visible(False)
clock = pygame.time.Clock()
STATUS_FONT = pygame.font.SysFont("monospace", 22)


# ================= FACE =================
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

eye_radius   = int(min(SCREEN_W, SCREEN_H) * 0.15)
pupil_radius = int(eye_radius * 0.35)

LEFT_EYE  = (int(SCREEN_W * 0.35), int(SCREEN_H * 0.36))
RIGHT_EYE = (int(SCREEN_W * 0.65), int(SCREEN_H * 0.36))
SMILE_Y   = int(SCREEN_H * 0.45)

pupil_x = pupil_y = 0
target_x = target_y = 0
think_angle = 0.0

def draw_eye(cx, cy, px, py):
    pygame.draw.circle(screen, (255, 255, 255), (cx, cy), eye_radius)
    pygame.draw.circle(screen, (0, 0, 0), (cx + px, cy + py), pupil_radius)


def draw_smile():
    cx = SCREEN_W // 2
    r  = int(SCREEN_W * 0.22)
    pts = [(cx + int(r * math.cos(a)), SMILE_Y + int(r * math.sin(a)))
           for a in np.linspace(math.radians(40), math.radians(100), 40)]
    pygame.draw.lines(screen, (220, 220, 220), False, pts, 15)

def draw_status_leds():
    pygame.draw.circle(screen, (0, 120, 255) if hand_present else (40, 40, 40), (40, 40),  12)
    pygame.draw.circle(screen, (0, 255, 0)   if is_speaking  else (40, 40, 40), (40, 75),  12)
    pygame.draw.circle(screen, (255, 165, 0) if is_thinking  else (40, 40, 40), (40, 110), 12)

def draw_detection(frame):
    frame = cv2.resize(frame, (SCREEN_W, SCREEN_H))
    rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    surf  = pygame.surfarray.make_surface(rgb.swapaxes(0, 1))
    screen.blit(surf, (0, 0))

# ================= MAIN LOOP =================
running = True
while running:
    for e in pygame.event.get():
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            running = False

    ret, frame = cap.read()
    if not ret:
        continue

    frame  = cv2.flip(frame, 1)
    rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    now          = time.time()
    current_hand = bool(result.multi_hand_landmarks)
    hand_present = current_hand

    if current_hand and not last_hand_state:
        if not is_speaking and not is_thinking and now - last_interaction_time > INTERACTION_COOLDOWN:
            speak(HAND_GREETINGS[hand_greet_index])
            hand_greet_index = (hand_greet_index + 1) % len(HAND_GREETINGS)
            last_interaction_time = now

    last_hand_state = current_hand

    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    if len(faces):
        x, y, w, h = faces[0]
        fx, fy = x + w // 2, y + h // 2
        fh, fw = gray.shape
        target_x = int(-(fx - fw / 2) / (fw / 2) * eye_radius * 0.25)
        target_y = int(-(fy - fh / 2) / (fh / 2) * eye_radius * 0.25)

    pupil_x += (target_x - pupil_x) * 0.1
    pupil_y += (target_y - pupil_y) * 0.1

    if show_detection:
        draw_detection(frame)
        draw_status_leds()
    else:
        screen.fill((10, 10, 30))    

        draw_eye(*LEFT_EYE,  int(pupil_x), int(pupil_y))
        draw_eye(*RIGHT_EYE, int(pupil_x), int(pupil_y))

        if is_thinking:
            thinking_surf = STATUS_FONT.render("( thinking... )", True, (160, 160, 160))
            thinking_rect = thinking_surf.get_rect(center=(SCREEN_W // 2, SCREEN_H - 40))
            screen.blit(thinking_surf, thinking_rect)

        draw_smile()
        draw_status_leds()

    pygame.display.flip()
    clock.tick(30)

cap.release()
pygame.quit()