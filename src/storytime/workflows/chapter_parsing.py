from junjo import BaseState, BaseStore, Node, Graph, Workflow, Edge
from storytime.models import Chapter, CharacterCatalogue, TextSegment
from storytime.services.character_analyzer import CharacterAnalyzer
from typing import Optional
from pathlib import Path
import json
import os

# --- State ---
class ChapterParsingState(BaseState):
    chapter_text: Optional[str] = None
    file_path: Optional[str] = None  # New: allow file input
    chapter_number: Optional[int] = None
    title: Optional[str] = None
    character_catalogue: Optional[CharacterCatalogue] = None
    segments: Optional[list[TextSegment]] = None
    chapter: Optional[Chapter] = None
    # Add more fields as needed (e.g., error, status)

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

class AnalyzeCharactersNode(Node[ChapterParsingStore]):
    """Node to analyze characters in the chapter text."""
    async def service(self, store: ChapterParsingStore) -> None:
        state = await store.get_state()
        if not state.chapter_text:
            raise ValueError("chapter_text must be loaded before character analysis.")
        catalogue = state.character_catalogue or CharacterCatalogue()
        analyzer = CharacterAnalyzer()
        existing_names = catalogue.get_character_names()
        new_characters = analyzer.analyze_characters(state.chapter_text, existing_names)
        for character in new_characters:
            catalogue.add_character(character)
        await store.set_state({"character_catalogue": catalogue})

class ParseSegmentsNode(Node[ChapterParsingStore]):
    """Node to parse chapter text into segments using Gemini."""
    async def service(self, store: ChapterParsingStore) -> None:
        state = await store.get_state()
        if not state.chapter_text:
            raise ValueError("chapter_text must be loaded before parsing segments.")
        # Directly implement the parsing logic here or call the new workflow logic
        # For now, raise NotImplementedError to signal this needs to be replaced
        raise NotImplementedError("Parsing logic should be implemented here using Junjo-native approach.")
        # await store.set_state({
        #     "chapter": chapter,
        #     "segments": chapter.segments
        # })

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
        if state.chapter:
            with (chapter_data_path / "segments.json").open("w", encoding="utf-8") as f:
                json.dump(state.chapter.model_dump(), f, indent=2, ensure_ascii=False)
        # Save character catalogue
        if state.character_catalogue:
            with (chapter_data_path / "characters.json").open("w", encoding="utf-8") as f:
                json.dump(state.character_catalogue.model_dump(), f, indent=2, ensure_ascii=False)

# --- Graph and Workflow ---
load_text_node = LoadTextNode()
analyze_characters_node = AnalyzeCharactersNode()
parse_segments_node = ParseSegmentsNode()
save_results_node = SaveResultsNode()

graph = Graph(
    source=load_text_node,
    sink=save_results_node,
    edges=[
        Edge(tail=load_text_node, head=analyze_characters_node),
        Edge(tail=analyze_characters_node, head=parse_segments_node),
        Edge(tail=parse_segments_node, head=save_results_node),
    ]
)

workflow = Workflow[
    ChapterParsingState, ChapterParsingStore
](
    name="Chapter Parsing Pipeline",
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