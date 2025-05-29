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
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore[import]
except ImportError:
    from opentelemetry.exporter.otlp.trace_exporter import OTLPSpanExporter  # type: ignore[import]

# --- OpenTelemetry Initialization ---
trace.set_tracer_provider(TracerProvider())
otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
)
# type: ignore[attr-defined] for add_span_processor (OpenTelemetry SDK)
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))  # type: ignore[attr-defined]
tracer = trace.get_tracer(__name__)

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
        with tracer.start_as_current_span("LoadTextNode") as span:
            state = await store.get_state()
            
            node_inputs: dict[str, Any] = {
                "has_chapter_text_initially": bool(state.chapter_text),
                "file_path": str(state.file_path or "")
            }
            span.set_attribute("braintrust.input", json.dumps(node_inputs))
            
            node_outputs: dict[str, Any] = {}

            try:
                if state.chapter_text:
                    node_outputs["text_loaded_from_state"] = True
                    node_outputs["text_summary"] = str(state.chapter_text[:200] + "..." if state.chapter_text and len(state.chapter_text) > 200 else state.chapter_text or "")
                    span.set_attribute("braintrust.output", json.dumps(node_outputs))
                    return

                if state.file_path:
                    text = Path(state.file_path).read_text(encoding="utf-8")
                    await store.set_state({"chapter_text": text}) 
                    node_outputs["text_loaded_from_file"] = True
                    node_outputs["text_summary"] = str(text[:200] + "..." if len(text) > 200 else text)
                else:
                    raise ValueError("No chapter_text or file_path provided in state.")
                
                span.set_attribute("braintrust.output", json.dumps(node_outputs))

            except Exception as e:
                error_message = f"Failed to load text: {e}"
                node_outputs["error"] = error_message
                span.set_attribute("error", error_message) 
                await store.set_state({"error": error_message})
                span.set_attribute("braintrust.output", json.dumps(node_outputs))
                raise

class ChunkTextNode(Node[ChapterParsingStore]):
    """Node to split chapter text into manageable chunks for LLM processing."""
    async def service(self, store: ChapterParsingStore) -> None:
        with tracer.start_as_current_span("ChunkTextNode") as span:
            state = await store.get_state()
            
            node_inputs: dict[str, Any] = {"has_chapter_text": bool(state.chapter_text)}
            if state.chapter_text:
                node_inputs["chapter_text_length"] = len(state.chapter_text)
                node_inputs["chapter_text_summary"] = str(state.chapter_text[:200] + "..." if len(state.chapter_text) > 200 else state.chapter_text)
            span.set_attribute("braintrust.input", json.dumps(node_inputs))

            node_outputs: dict[str, Any] = {}
            try:
                if not state.chapter_text:
                    raise ValueError("chapter_text must be loaded before chunking.")
                
                text = state.chapter_text
                max_chunk_size = 800
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
                if len(chunks) == 1 and len(chunks[0]) > max_chunk_size:
                    # Fallback for very long single paragraphs
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
                
                node_outputs["num_chunks"] = len(chunks)
                if chunks:
                    node_outputs["first_chunk_summary"] = str(chunks[0][:200] + "..." if len(chunks[0]) > 200 else chunks[0])
                
                await store.set_state({"chunks": chunks})
                span.set_attribute("braintrust.output", json.dumps(node_outputs))

            except Exception as e:
                error_message = f"Error in ChunkTextNode: {e}"
                node_outputs["error"] = error_message
                span.set_attribute("error", error_message)
                await store.set_state({"error": error_message})
                span.set_attribute("braintrust.output", json.dumps(node_outputs))
                raise

class PromptConstructionNode(Node[ChapterParsingStore]):
    """Node to build Gemini prompts for each chunk."""
    async def service(self, store: ChapterParsingStore) -> None:
        with tracer.start_as_current_span("PromptConstructionNode") as span:
            state = await store.get_state()

            node_inputs: dict[str, Any] = {"num_chunks": len(state.chunks) if state.chunks else 0}
            if state.chunks:
                node_inputs["first_chunk_summary"] = str(state.chunks[0][:200] + "..." if state.chunks[0] and len(state.chunks[0]) > 200 else state.chunks[0] or "")
            span.set_attribute("braintrust.input", json.dumps(node_inputs))
            
            node_outputs: dict[str, Any] = {}
            try:
                if not state.chunks:
                    raise ValueError("chunks must be set before prompt construction.")
                
                prompts = []
                for chunk in state.chunks:
                    prompt = f'''
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
'''
                    prompts.append(prompt.strip())
                
                node_outputs["num_prompts"] = len(prompts)
                if prompts:
                    node_outputs["first_prompt_summary"] = str(prompts[0][:200] + "..." if prompts[0] and len(prompts[0]) > 200 else prompts[0] or "")
                
                await store.set_state({"prompts": prompts})
                span.set_attribute("braintrust.output", json.dumps(node_outputs))

            except Exception as e:
                error_message = f"Error in PromptConstructionNode: {e}"
                node_outputs["error"] = error_message
                span.set_attribute("error", error_message)
                await store.set_state({"error": error_message})
                span.set_attribute("braintrust.output", json.dumps(node_outputs))
                raise

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
        with tracer.start_as_current_span("GeminiApiNode") as span:
            state = await store.get_state()

            node_inputs: dict[str, Any] = {"num_prompts": len(state.prompts) if state.prompts else 0}
            if state.prompts:
                 node_inputs["first_prompt_summary"] = str(state.prompts[0][:200] + "..." if state.prompts[0] and len(state.prompts[0]) > 200 else state.prompts[0] or "")
            span.set_attribute("braintrust.input", json.dumps(node_inputs))

            node_outputs: dict[str, Any] = {}
            try:
                if not state.prompts:
                    raise ValueError("prompts must be set before Gemini API calls.")
                
                api_key = os.getenv("GOOGLE_API_KEY")
                if not api_key:
                    raise ValueError("GOOGLE_API_KEY not set in environment.")
                
                model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
                tasks = [call_gemini_api(prompt, model_name, api_key) for prompt in state.prompts]
                raw_responses = await asyncio.gather(*tasks)
                
                node_outputs["num_responses"] = len(raw_responses)
                if raw_responses:
                    node_outputs["first_response_summary"] = str(str(raw_responses[0])[:200] + "..." if raw_responses[0] and len(str(raw_responses[0])) > 200 else str(raw_responses[0]) or "")
                
                await store.set_state({"raw_responses": raw_responses})
                span.set_attribute("braintrust.output", json.dumps(node_outputs))

            except Exception as e:
                error_message = f"Error in GeminiApiNode: {e}"
                node_outputs["error"] = error_message
                span.set_attribute("error", error_message)
                await store.set_state({"error": error_message}) # Ensure error is in store
                span.set_attribute("braintrust.output", json.dumps(node_outputs))
                raise

class ParseSegmentsNode(Node[ChapterParsingStore]):
    """Node to parse and validate JSON from Gemini, flatten and renumber segments. Retries failed chunks and validates schema."""
    async def service(self, store: ChapterParsingStore) -> None:
        with tracer.start_as_current_span("ParseSegmentsNode") as span:
            state = await store.get_state()

            node_inputs: dict[str, Any] = {
                "num_raw_responses": len(state.raw_responses) if state.raw_responses else 0,
                "num_prompts": len(state.prompts) if state.prompts else 0
            }
            if state.raw_responses:
                node_inputs["first_raw_response_summary"] = str(str(state.raw_responses[0])[:200] + "..." if state.raw_responses[0] and len(str(state.raw_responses[0])) > 200 else str(state.raw_responses[0]) or "")
            span.set_attribute("braintrust.input", json.dumps(node_inputs))

            node_outputs: dict[str, Any] = {}
            all_segments: List[TextSegment] = [] # Define all_segments at a scope visible to the finally/except block if needed for output
            try:
                if not state.raw_responses or not state.prompts:
                    raise ValueError("raw_responses and prompts must be set before parsing segments.")
                
                seq = 1
                api_key = os.getenv("GOOGLE_API_KEY")
                if not api_key:
                    raise ValueError("GOOGLE_API_KEY not set in environment.")
                model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

                for idx, (raw, prompt) in enumerate(zip(state.raw_responses, state.prompts)):
                    for attempt in range(3): # Max 3 attempts
                        try:
                            response_text = raw.strip() if attempt == 0 else await call_gemini_api(prompt, model_name, api_key)
                            match = re.search(r'([\{\[].*)', response_text, re.DOTALL) # Corrected regex
                            if match:
                                response_text = match.group(1)
                            
                            response_text = re.sub(r',([ \t\r\n]*[\]\}])', r'\1', response_text) # remove trailing commas
                            
                            # Attempt to fix incomplete JSON (common with LLMs)
                            n_open_curly = response_text.count('{')
                            n_close_curly = response_text.count('}')
                            if n_open_curly > n_close_curly:
                                response_text += '}' * (n_open_curly - n_close_curly)
                            
                            n_open_square = response_text.count('[')
                            n_close_square = response_text.count(']')
                            if n_open_square > n_close_square:
                                response_text += ']' * (n_open_square - n_close_square)

                            data = json.loads(response_text)
                            if isinstance(data, dict) and "segments" in data:
                                segments_data = data["segments"]
                            elif isinstance(data, list):
                                segments_data = data # Assumes the list itself is the segments_data
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
                                    speaker_name = str(speaker) # Ensure speaker_name is a string
                                try:
                                    seg = TextSegment(
                                        text=str(seg_dict.get("text", "")), # Ensure text is a string
                                        speaker_type=speaker_type,
                                        speaker_name=speaker_name,
                                        sequence_number=seq,
                                        voice_hint=seg_dict.get("voice_hint"),
                                        emotion=seg_dict.get("emotion"),
                                        instruction=seg_dict.get("instruction"),
                                    )
                                    all_segments.append(seg)
                                    seq += 1
                                except ValidationError as ve_seg:
                                    span.add_event("segment_schema_error", {"chunk_idx": idx, "segment_data": str(seg_dict), "error": str(ve_seg)})
                                    continue # Skip this segment
                            break # Success for this chunk
                        except Exception as e_attempt:
                            if attempt == 2: # Last attempt failed
                                span.add_event("parse_chunk_error_final", {"chunk_idx": idx, "error": str(e_attempt), "raw_response_snippet": raw[:100]})
                                # Optionally, decide if this chunk failure is critical for the whole node
                                # For now, we continue to process other chunks
                                break # Break from retry loop for this chunk
                            else:
                                span.add_event("parse_chunk_retry", {"chunk_idx": idx, "attempt": attempt + 1, "error": str(e_attempt)})
                                await asyncio.sleep(0.5) # Wait before retrying
                
                node_outputs["num_segments"] = len(all_segments)
                if all_segments:
                    try:
                        first_segment_json = all_segments[0].model_dump_json()
                        node_outputs["first_segment_summary"] = str(first_segment_json[:200] + "..." if len(first_segment_json) > 200 else first_segment_json)
                    except Exception as e_dump: # Catch error from model_dump_json
                        node_outputs["first_segment_summary_error"] = str(e_dump)
                
                await store.set_state({"segments": all_segments})
                span.set_attribute("braintrust.output", json.dumps(node_outputs))

            except Exception as e:
                error_message = f"Error in ParseSegmentsNode: {e}"
                node_outputs["error"] = error_message
                node_outputs["num_segments_before_error"] = len(all_segments) # Log how many were processed
                span.set_attribute("error", error_message)
                await store.set_state({"error": error_message, "segments": all_segments}) # Save partial if any
                span.set_attribute("braintrust.output", json.dumps(node_outputs))
                raise

class MergeSegmentsNode(Node[ChapterParsingStore]):
    """Node to merge all segments, validate, and build the Chapter model."""
    async def service(self, store: ChapterParsingStore) -> None:
        with tracer.start_as_current_span("MergeSegmentsNode") as span:
            state = await store.get_state()

            node_inputs: dict[str, Any] = {"num_segments": len(state.segments) if state.segments else 0}
            if state.segments:
                try:
                    first_segment_json = state.segments[0].model_dump_json()
                    node_inputs["first_segment_summary"] = str(first_segment_json[:200] + "..." if len(first_segment_json) > 200 else first_segment_json)
                except Exception as e_dump:
                    node_inputs["first_segment_summary_error"] = str(e_dump)
            span.set_attribute("braintrust.input", json.dumps(node_inputs))

            node_outputs: dict[str, Any] = {}
            try:
                if not state.segments: # Check if segments list is None or empty
                    raise ValueError("segments must be set and non-empty before merging into Chapter.")
                if len(state.segments) == 0: # Explicit check for empty list
                     raise ValueError("No segments produced: at least one segment is required to build a Chapter.")

                chapter = Chapter(
                    chapter_number=state.chapter_number or 1,
                    title=state.title,
                    segments=state.segments
                )
                await store.set_state({"chapter": chapter})
                
                node_outputs["chapter_number"] = chapter.chapter_number
                node_outputs["chapter_title"] = str(chapter.title or "")
                node_outputs["num_segments_in_chapter"] = len(chapter.segments)
                span.set_attribute("braintrust.output", json.dumps(node_outputs))

            except Exception as e:
                error_message = f"Error in MergeSegmentsNode: {e}"
                node_outputs["error"] = error_message
                span.set_attribute("error", error_message)
                await store.set_state({"error": error_message})
                span.set_attribute("braintrust.output", json.dumps(node_outputs))
                raise

class ErrorHandlingNode(Node[ChapterParsingStore]):
    """Node for error state, retry/fallback logic."""
    async def service(self, store: ChapterParsingStore) -> None:
        with tracer.start_as_current_span("ErrorHandlingNode") as span:
            state = await store.get_state()
            
            node_inputs: dict[str, Any] = {"error_message_from_state": str(state.error or "No error message present in state.")}
            span.set_attribute("braintrust.input", json.dumps(node_inputs))
            
            node_outputs: dict[str, Any] = {"processed_error": str(state.error or "") if state.error else None}
            if state.error:
                span.set_attribute("error", str(state.error)) # Standard way to flag error in span
                print(f"[Junjo ErrorHandlingNode] Error in workflow: {state.error}")
                node_outputs["status"] = "Error processed"
            else:
                node_outputs["status"] = "No error to process"
            
            span.set_attribute("braintrust.output", json.dumps(node_outputs))
            # This node typically doesn't change state unless it resolves an error,
            # or re-raises if it cannot handle it. For now, it's informational.

class SaveResultsNode(Node[ChapterParsingStore]):
    """Node to save parsed results to disk (optional/debug)."""
    async def service(self, store: ChapterParsingStore) -> None:
        with tracer.start_as_current_span("SaveResultsNode") as span:
            state = await store.get_state()

            node_inputs: dict[str, Any] = {
                "has_chapter_text": bool(state.chapter_text),
                "num_segments": len(state.segments) if state.segments else 0,
                "has_chapter": bool(state.chapter),
                "has_character_catalogue": bool(state.character_catalogue)
            }
            span.set_attribute("braintrust.input", json.dumps(node_inputs))

            node_outputs: dict[str, Any] = {}
            try:
                output_dir_env = os.getenv("CHAPTER_OUTPUT_DIR", "chapter_data")
                chapter_number = state.chapter_number or 1
                chapter_data_path = Path(output_dir_env) / f"chapter_{chapter_number:02d}"
                chapter_data_path.mkdir(parents=True, exist_ok=True)
                
                node_outputs["output_dir"] = str(chapter_data_path)
                files_saved: List[str] = []
                
                if state.chapter_text:
                    (chapter_data_path / "text.txt").write_text(state.chapter_text, encoding="utf-8")
                    files_saved.append("text.txt")
                if state.segments:
                    with (chapter_data_path / "segments.json").open("w", encoding="utf-8") as f:
                        json.dump([s.model_dump() for s in state.segments], f, indent=2, ensure_ascii=False)
                    files_saved.append("segments.json")
                if state.chapter:
                    with (chapter_data_path / "chapter.json").open("w", encoding="utf-8") as f:
                        json.dump(state.chapter.model_dump(), f, indent=2, ensure_ascii=False)
                    files_saved.append("chapter.json")
                if state.character_catalogue: # This was not in the original inputs to log, adding output logic
                    with (chapter_data_path / "characters.json").open("w", encoding="utf-8") as f:
                        json.dump(state.character_catalogue.model_dump(), f, indent=2, ensure_ascii=False)
                    files_saved.append("characters.json")
                
                node_outputs["files_saved"] = files_saved if files_saved else [] # Ensure it's a list
                span.set_attribute("braintrust.output", json.dumps(node_outputs))

            except Exception as e:
                error_message = f"Error in SaveResultsNode: {e}"
                node_outputs["error"] = error_message
                span.set_attribute("error", error_message)
                # No store.set_state for error here as this is a sink node, but log it in output
                span.set_attribute("braintrust.output", json.dumps(node_outputs))
                # Optionally re-raise if saving is critical, or just log
                print(f"Error during SaveResultsNode: {error_message}")


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