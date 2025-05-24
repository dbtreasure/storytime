# Setup Instructions

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Get API Keys

### Google Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy the key

### OpenAI API Key (for later TTS steps)

1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy the key

## 3. Set Environment Variables

### Option A: Export in terminal

```bash
export GOOGLE_API_KEY="your_google_api_key_here"
export OPENAI_API_KEY="your_openai_api_key_here"
```

### Option B: Create a .env file

Create a file named `.env` in the project root:

```
GOOGLE_API_KEY=your_google_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

## 4. Test the Parser

```bash
python test_parser.py
```

This will:

- Parse `chapter_1.txt` using Gemini API
- Create structured `TextSegment` objects
- Save the result to `parsed_chapter_1.json`
- Show statistics about the parsing

## Expected Output

You should see:

- Number of segments created
- List of characters found
- Sample segments with speaker attribution
- Voice hints and emotional context
- Dialogue vs narration statistics
