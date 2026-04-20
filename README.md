# Real-Time-Human-Robot-Interaction-System
Mister Robo is a real-time interactive robot interface that combines **computer vision, speech recognition, and conversational AI** to create a natural human-robot interaction experience.

The system can see, listen, think, and respond with expressive visual feedback and voice output.

---

## 🚀 Features

* 🎤 **Voice Interaction**
  Uses offline speech recognition to understand user input in real time.

* 🧠 **Conversational AI (Ollama)**
  Generates intelligent, short, human-like responses using a local LLM.

* 🔊 **Text-to-Speech Output**
  Converts responses into spoken audio.

* 👁️ **Vision System**

  * Face tracking for eye movement
  * Hand detection for interaction triggers

* 😊 **Expressive Robot Face (Pygame)**

  * Eye tracking
  * Thinking animation
  * Status indicators (listening, speaking, thinking)

* ⚡ **Real-Time Multithreaded Architecture**
  Separate threads for:

  * audio processing
  * AI reasoning
  * speech output

---

## 🧱 System Architecture

```
User Speech → Vosk (Speech Recognition)
            → Ollama (LLM Reasoning)
            → gTTS (Speech Output)
            → Pygame Face (Visual Feedback)

Camera → OpenCV + MediaPipe → Face & Hand Detection
```

---

## 🛠️ Tech Stack

* **Python 3.10**
* OpenCV
* MediaPipe
* Vosk (offline speech recognition)
* Ollama (local LLM)
* gTTS + mpg123 (speech output)
* Pygame (UI rendering)

---

## ▶️ Setup

### 1. Create environment

```bash
python3.10 -m venv robo_env
source robo_env/bin/activate
```

### 2. Install dependencies

```bash
pip install opencv-python numpy pygame gTTS vosk sounddevice mediapipe
```

### 3. Install system packages

```bash
sudo apt install mpg123 portaudio19-dev
```

### 4. Download Vosk model

```bash
mkdir -p models
cd models
wget https://alphacephei.com/vosk/models/vosk-model-en-in-0.5.zip
unzip vosk-model-en-in-0.5.zip
```

### 5. Run Ollama

Make sure Ollama is running locally:

```bash
ollama run llama3.2
```

### 6. Run the project

```bash
python robot_ollama.py
```

---

## ⚠️ Notes

* Requires a working microphone and camera
* Designed for **real-time interaction**, so performance depends on hardware
* Uses local AI (Ollama), no internet needed for responses

---
