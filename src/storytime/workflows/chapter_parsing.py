from junjo import BaseState, BaseStore, Node, Graph, Workflow, Edge
from storytime.models import Chapter, CharacterCatalogue, TextSegment, SpeakerType
from storytime.services.character_analyzer import CharacterAnalyzer
from typing import Optional, List, Any
from pathlib import Path
import json
import os
import google.generativeai as genai
import re
from google.generativeai.types import GenerationConfig
from pydantic import ValidationError

# --- State ---
class ChapterParsingState(BaseState):
    chapter_text: Optional[str] = None
    file_path: Optional[str] = None
    chapter_number: Optional[int] = None
    title: Optional[str] = None
    character_catalogue: Optional[CharacterCatalogue] = None
    chunks: Optional[List[str]] = None
    prompts: Optional[List[str]] = None
    raw_responses: Optional[List[Any]] = None
    segments: Optional[List[TextSegment]] = None
    chapter: Optional[Chapter] = None
    error: Optional[str] = None
    # Add more fields as needed

# --- Store ---
class ChapterParsingStore(BaseStore[ChapterParsingState]):
    """Store for managing chapter parsing state."""
    pass

# --- Nodes ---
class LoadTextNode(Node[ChapterParsingStore]):
    """Node to load chapter text from file or input."""
    async def service(self, store: ChapterParsingStore) -> None:
        state = await store.get_state()
        if state.chapter_text:
            return  # Already loaded
        if state.file_path:
            text = Path(state.file_path).read_text(encoding="utf-8")
            await store.set_state({"chapter_text": text})
        else:
            raise ValueError("No chapter_text or file_path provided in state.")

class ChunkTextNode(Node[ChapterParsingStore]):
    """Node to split chapter text into manageable chunks for LLM processing."""
    async def service(self, store: ChapterParsingStore) -> None:
        state = await store.get_state()
        if not state.chapter_text:
            raise ValueError("chapter_text must be loaded before chunking.")
        text = state.chapter_text
        max_chunk_size = 800
        # Try to split by paragraphs first
        paragraphs = text.split("\n\n")
        chunks = []
        current = ""
        for paragraph in paragraphs:
            if len(current) + len(paragraph) + 2 > max_chunk_size and current:
                chunks.append(current.strip())
                current = paragraph
            else:
                current = f"{current}\n\n{paragraph}" if current else paragraph
        if current:
            chunks.append(current.strip())
        # Fallback to sentence splitting if only one chunk
        if len(chunks) == 1 and len(chunks[0]) > max_chunk_size:
            sentences = text.split(". ")
            chunks = []
            current = ""
            for i, sentence in enumerate(sentences):
                if i < len(sentences) - 1:
                    sentence += ". "
                if len(current) + len(sentence) > max_chunk_size and current:
                    chunks.append(current.strip())
                    current = sentence
                else:
                    current += sentence
            if current:
                chunks.append(current.strip())
        await store.set_state({"chunks": chunks})

class PromptConstructionNode(Node[ChapterParsingStore]):
    """Node to build Gemini prompts for each chunk."""
    async def service(self, store: ChapterParsingStore) -> None:
        state = await store.get_state()
        if not state.chunks:
            raise ValueError("chunks must be set before prompt construction.")
        prompts = []
        for chunk in state.chunks:
            prompt = f"""
### ROLE AND OBJECTIVE ###
You are a professional audiobook dialogue separator with expertise in industry-standard voice acting practices. Your goal is to parse novel text into precisely structured segments that follow professional audiobook conventions where dialogue and narrative descriptions are read by different voice actors.

### CHAPTER CONTEXT ###
Chapter Number: {state.chapter_number or 1}
Title: {state.title or ''}

### CHAPTER TEXT ###
{chunk}

### INSTRUCTIONS ###
• Segment the text as described above.
• Return ONLY valid JSON, with all required fields, and no extra text, comments, or markdown/code fences.
• The response must be a single valid JSON object with this schema:
  {{ "segments": [{{ "speaker": "narrator|character name", "text": "..." }}] }}
• Do not include any explanations, comments, or formatting outside the JSON object.
"""
            prompts.append(prompt.strip())
        await store.set_state({"prompts": prompts})

async def call_gemini_api(prompt: str, model_name: str, api_key: str) -> str:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig
    genai.configure(api_key=api_key)  # type: ignore[attr-defined]
    model = genai.GenerativeModel(model_name)  # type: ignore[attr-defined]
    import asyncio
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: model.generate_content(
            prompt,
            generation_config=GenerationConfig(response_mime_type="application/json")
        )
    )
    return response.text

class GeminiApiNode(Node[ChapterParsingStore]):
    """Node to make async Gemini API calls for each prompt/chunk (parallelizable)."""
    async def service(self, store: ChapterParsingStore) -> None:
        import os
        state = await store.get_state()
        if not state.prompts:
            raise ValueError("prompts must be set before Gemini API calls.")
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            await store.set_state({"error": "GOOGLE_API_KEY not set in environment."})
            raise ValueError("GOOGLE_API_KEY not set in environment.")
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        tasks = [call_gemini_api(prompt, model_name, api_key) for prompt in state.prompts]
        raw_responses = await asyncio.gather(*tasks)
        await store.set_state({"raw_responses": raw_responses})

class ParseSegmentsNode(Node[ChapterParsingStore]):
    """Node to parse and validate JSON from Gemini, flatten and renumber segments. Retries failed chunks and validates schema."""
    async def service(self, store: ChapterParsingStore) -> None:
        import json
        from storytime.models import TextSegment, SpeakerType
        import re
        import os
        import asyncio
        state = await store.get_state()
        if not state.raw_responses or not state.prompts:
            raise ValueError("raw_responses and prompts must be set before parsing segments.")
        all_segments = []
        seq = 1
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            await store.set_state({"error": "GOOGLE_API_KEY not set in environment."})
            raise ValueError("GOOGLE_API_KEY not set in environment.")
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        for idx, (raw, prompt) in enumerate(zip(state.raw_responses, state.prompts)):
            for attempt in range(3):
                try:
                    response_text = raw.strip() if attempt == 0 else await call_gemini_api(prompt, model_name, api_key)
                    # --- Robust JSON fixup ---
                    match = re.search(r'([\[{].*)', response_text, re.DOTALL)
                    if match:
                        response_text = match.group(1)
                    response_text = re.sub(r',([ \t\r\n]*[\]}])', r'\1', response_text)
                    n_open = response_text.count('{')
                    n_close = response_text.count('}')
                    if n_open > n_close:
                        response_text += '}' * (n_open - n_close)
                    n_open = response_text.count('[')
                    n_close = response_text.count(']')
                    if n_open > n_close:
                        response_text += ']' * (n_open - n_close)
                    data = json.loads(response_text)
                    # Accept either a dict with 'segments' or a list
                    if isinstance(data, dict) and "segments" in data:
                        segments_data = data["segments"]
                    elif isinstance(data, list):
                        segments_data = data
                    else:
                        raise ValueError(f"Expected a list or dict with 'segments', got: {type(data)}")
                    if not isinstance(segments_data, list):
                        raise ValueError(f"Expected a list of segments, got: {type(segments_data)}")
                    for seg_dict in segments_data:
                        speaker = seg_dict.get("speaker", "narrator")
                        if isinstance(speaker, str) and speaker.strip().lower() == "narrator":
                            speaker_type = SpeakerType.NARRATOR
                            speaker_name = "narrator"
                        else:
                            speaker_type = SpeakerType.CHARACTER
                            speaker_name = str(speaker)
                        try:
                            seg = TextSegment(
                                text=str(seg_dict.get("text", "")),
                                speaker_type=speaker_type,
                                speaker_name=speaker_name,
                                sequence_number=seq,
                                voice_hint=seg_dict.get("voice_hint"),
                                emotion=seg_dict.get("emotion"),
                                instruction=seg_dict.get("instruction"),
                            )
                            all_segments.append(seg)
                            seq += 1
                        except ValidationError as ve:
                            print(f"[SCHEMA ERROR] Invalid segment at chunk {idx}, seq {seq}: {ve}\nSegment: {seg_dict}")
                            continue  # Skip invalid segment
                    break  # Success, break retry loop
                except Exception as e:
                    if attempt == 2:
                        print(f"[ERROR] Failed to parse Gemini response {idx} after 3 attempts: {e}\nRaw response: {raw}")
                        await store.set_state({"error": f"Error parsing Gemini response {idx} after 3 attempts: {e}"})
                        continue  # Skip this chunk
                    else:
                        print(f"[WARN] Retry {attempt+1} for Gemini response {idx} due to: {e}")
                        await asyncio.sleep(0.5)
        await store.set_state({"segments": all_segments})

class MergeSegmentsNode(Node[ChapterParsingStore]):
    """Node to merge all segments, validate, and build the Chapter model."""
    async def service(self, store: ChapterParsingStore) -> None:
        from storytime.models import Chapter
        state = await store.get_state()
        if not state.segments:
            raise ValueError("segments must be set before merging into Chapter.")
        if len(state.segments) == 0:
            raise ValueError("No segments produced: at least one segment is required to build a Chapter.")
        chapter = Chapter(
            chapter_number=state.chapter_number or 1,
            title=state.title,
            segments=state.segments
        )
        await store.set_state({"chapter": chapter})

class ErrorHandlingNode(Node[ChapterParsingStore]):
    """Node for error state, retry/fallback logic."""
    async def service(self, store: ChapterParsingStore) -> None:
        state = await store.get_state()
        if state.error:
            # Log the error; in a real system, could trigger retries or alerts
            print(f"[Junjo ErrorHandlingNode] Error in workflow: {state.error}")
        # No-op for now

class SaveResultsNode(Node[ChapterParsingStore]):
    """Node to save parsed results to disk (optional/debug)."""
    async def service(self, store: ChapterParsingStore) -> None:
        state = await store.get_state()
        output_dir = os.getenv("CHAPTER_OUTPUT_DIR", "chapter_data")
        chapter_number = state.chapter_number or 1
        chapter_data_path = Path(output_dir) / f"chapter_{chapter_number:02d}"
        chapter_data_path.mkdir(parents=True, exist_ok=True)
        # Save raw text
        if state.chapter_text:
            (chapter_data_path / "text.txt").write_text(state.chapter_text, encoding="utf-8")
        # Save segments
        if state.segments:
            with (chapter_data_path / "segments.json").open("w", encoding="utf-8") as f:
                json.dump([s.model_dump() for s in state.segments], f, indent=2, ensure_ascii=False)
        # Save chapter
        if state.chapter:
            with (chapter_data_path / "chapter.json").open("w", encoding="utf-8") as f:
                json.dump(state.chapter.model_dump(), f, indent=2, ensure_ascii=False)
        # Save character catalogue
        if state.character_catalogue:
            with (chapter_data_path / "characters.json").open("w", encoding="utf-8") as f:
                json.dump(state.character_catalogue.model_dump(), f, indent=2, ensure_ascii=False)

# --- Graph and Workflow ---
load_text_node = LoadTextNode()
chunk_text_node = ChunkTextNode()
prompt_construction_node = PromptConstructionNode()
gemini_api_node = GeminiApiNode()
parse_segments_node = ParseSegmentsNode()
merge_segments_node = MergeSegmentsNode()
error_handling_node = ErrorHandlingNode()
save_results_node = SaveResultsNode()

graph = Graph(
    source=load_text_node,
    sink=save_results_node,
    edges=[
        Edge(tail=load_text_node, head=chunk_text_node),
        Edge(tail=chunk_text_node, head=prompt_construction_node),
        Edge(tail=prompt_construction_node, head=gemini_api_node),
        Edge(tail=gemini_api_node, head=parse_segments_node),
        Edge(tail=parse_segments_node, head=merge_segments_node),
        Edge(tail=merge_segments_node, head=save_results_node),
        # Optionally, add error handling edges as needed
    ]
)

workflow = Workflow[
    ChapterParsingState, ChapterParsingStore
](
    name="Chapter Parsing Pipeline (Junjo-Native)",
    graph=graph,
    store=ChapterParsingStore(initial_state=ChapterParsingState()),
)

# --- Minimal runner for local testing ---
import asyncio

async def main():
    # Example: set file_path, chapter_number, and title here
    file_path = "tests/fixtures/chapter_1.txt"  # Update as needed
    chapter_number = 1
    title = "Anna Pavlovna's Salon"
    await workflow.store.set_state({
        "file_path": file_path,
        "chapter_number": chapter_number,
        "title": title,
    })
    await workflow.execute()
    state = await workflow.get_state_json()
    print("Final workflow state:", state)

if __name__ == "__main__":
    asyncio.run(main()) 