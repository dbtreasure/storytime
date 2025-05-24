# 📚 StorytimeTTS - Novel to Audio Pipeline

Transform classic literature into immersive audiobooks using AI! This application parses novel text into structured segments and generates high-quality audio with character-specific voices.

## 🌟 Features

- **📖 Smart Text Parsing**: Uses Google Gemini to identify dialogue vs narration
- **🎭 Character Recognition**: Automatically detects speakers and assigns appropriate voices
- **🎙️ Multi-Voice Audio**: OpenAI TTS with different voices for each character
- **🎵 Structured Output**: Complete chapter MP3 + organized individual segments

## 🏗️ Architecture

```
Text Input → Gemini API → Structured Data → OpenAI TTS → Audio Files
                ↓              ↓             ↓
          [Character      [TextSegment    [MP3 Files
           Detection]      Objects]       + Playlist]
```

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd storytime
pip install -r requirements.txt
```

### 2. Get API Keys

- **Google Gemini**: [Get key here](https://makersuite.google.com/app/apikey)
- **OpenAI**: [Get key here](https://platform.openai.com/api-keys)

### 3. Set Environment Variables

```bash
export GOOGLE_API_KEY="your_google_api_key"
export OPENAI_API_KEY="your_openai_api_key"
```

### 4. Test the Pipeline

```bash
# Test parsing only (free)
python test_parser.py

# Test complete pipeline (uses credits)
python test_full_pipeline.py
```

## 📋 Core Components

### 🧠 Text Parser (`chapter_parser.py`)

- Analyzes novel text with Gemini AI
- Identifies speakers and emotional context
- Creates structured `TextSegment` objects

### 🎙️ TTS Generator (`tts_generator.py`)

- Converts segments to audio using OpenAI TTS
- Smart voice selection based on character traits
- Generates organized audio files and playlists

### 📊 Data Models (`models.py`)

- Pydantic models for type-safe data handling
- Structured representation of chapters and segments

## 🎭 Voice Mapping

| Character Type     | Voice   | Description          |
| ------------------ | ------- | -------------------- |
| Narrator           | `echo`  | Neutral, clear voice |
| Male Characters    | `onyx`  | Deep male voice      |
| Female Characters  | `nova`  | Clear female voice   |
| Elderly Characters | `fable` | Distinguished voice  |
| Default            | `alloy` | Fallback voice       |

## 💰 Cost Estimates

### Gemini API (Parsing)

- **Free tier**: 15 requests/minute
- **Cost**: $0.00 for moderate usage

### OpenAI TTS

- **Rate**: $0.015 per 1,000 characters
- **War & Peace Chapter 1**: ~$0.50-1.00
- **Full novel**: ~$50-100

## 📁 Output Structure

```
audio_output/
├── chapter_01_complete.mp3          (Complete chapter audio)
├── chapter_01/                      (Individual segments)
│   ├── ch01_001_Anna_Pavlovna_Scherer.mp3
│   ├── ch01_002_narrator.mp3
│   ├── ch01_003_Prince_Vasili_Kuragin.mp3
│   └── chapter_01_playlist.m3u
└── chapter_02_complete.mp3
```

## 🔧 Advanced Usage

### Generate Full Chapter Audio

```python
from chapter_parser import ChapterParser
from tts_generator import generate_chapter_audio

# Parse chapter
parser = ChapterParser()
chapter = parser.parse_chapter_from_file("chapter_1.txt", 1)

# Generate all audio
audio_files = generate_chapter_audio(chapter)
print(f"Generated {len(audio_files)} files")
```

### Custom Voice Selection

```python
generator = TTSGenerator()
generator.voice_mapping["male"] = "fable"  # Use distinguished voice for males
```

### Batch Processing

```python
for i in range(1, 11):  # Process chapters 1-10
    chapter = parser.parse_chapter_from_file(f"chapter_{i}.txt", i)
    generate_chapter_audio(chapter, output_dir=f"book_audio/chapter_{i}")
```

## 📊 Example Output

### Chapter Analysis

```
✅ Successfully parsed Chapter 1: Anna Pavlovna's Salon
📊 Total segments: 35
👥 Characters found: Prince Vasíli Kurágin, Anna Pávlovna Schérer
📈 Analysis:
   Narrator segments: 11
   Character dialogue segments: 24
   Dialogue ratio: 68.6%
```

### Audio Generation

```
🎵 Generating audio for Chapter 1: Anna Pavlovna's Salon
🎙️  Generating audio for segment 1: [Anna Pávlovna Schérer]
   Voice: nova | Text: "Well, Prince, so Genoa and Lucca are now just family estates...
   ✅ Saved: ch01_001_Anna_Pavlovna_Scherer.mp3
```

## 🛠️ Configuration

### Available Models

- **Gemini**: `gemini-1.5-flash` (default)
- **OpenAI TTS**: `tts-1` (default), `tts-1-hd` (higher quality)

### Audio Formats

- MP3 (default), WAV, FLAC, AAC, Opus, PCM

### Voice Options

- `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`

## 🐛 Troubleshooting

### Common Issues

1. **"'str' object has no attribute 'value'"**

   - Fixed in current version - Pydantic enum handling

2. **API Rate Limits**

   - Gemini: 15 requests/minute (free tier)
   - OpenAI: 50 requests/minute (paid tier)

3. **High Costs**
   - Test with small samples first
   - Monitor character counts
   - Use `tts-1` instead of `tts-1-hd` for testing

## 📚 Example with War and Peace

The included `chapter_1.txt` contains the opening of Tolstoy's War and Peace, demonstrating:

- Complex character dialogue
- French aristocratic society
- Multiple speakers in conversation
- Rich descriptive narration

Perfect for testing the AI's ability to parse classical literature!

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 📄 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- **Google Gemini** for advanced text analysis
- **OpenAI** for high-quality text-to-speech
- **Tolstoy** for the timeless literature
- **Pydantic** for type-safe data models

---

**Ready to bring classic literature to life? Start with `python test_full_pipeline.py`!** 🎧📚
