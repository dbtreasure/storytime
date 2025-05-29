from __future__ import annotations

"""Junjo-native fan-out workflow that turns a parsed Chapter object into audio.

Nodes:
1. InitAudioNode – puts (chapter, tts_generator) in state.
2. GenerateSegmentAudioNode – one per TextSegment, runs in parallel via ThreadPoolExecutor.
3. StitchChapterNode – waits for all audio paths, stitches & creates playlist, updates state.

Usage::

    from storytime.workflows.audio_generation import build_audio_workflow
    wf = build_audio_workflow(chapter, tts_generator, max_concurrency=8)
    await wf.execute()
    state = await wf.get_state_json()
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from typing import Any, Dict, List
import time

from junjo import BaseState, BaseStore, Edge, Graph, Node, Workflow  # type: ignore
from opentelemetry import trace
from storytime.models import Chapter, TextSegment
from storytime.services.tts_generator import TTSGenerator

tracer = trace.get_tracer(__name__)

# ---------------------------------------------------------------------------
# State / Store
# ---------------------------------------------------------------------------

class AudioGenerationState(BaseState):
    chapter: Chapter | None = None
    tts_generator: TTSGenerator | None = None
    # segment_key -> audio path
    audio_paths: Dict[str, str] | None = None
    stitched_path: str | None = None
    playlist_path: str | None = None
    error: str | None = None


class AudioGenerationStore(BaseStore[AudioGenerationState]):
    pass


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

class InitAudioNode(Node[AudioGenerationStore]):
    """Store the Chapter and TTSGenerator in state so fan-out nodes can use them."""

    def __init__(self, chapter: Chapter, tts: TTSGenerator):
        super().__init__()
        self._chapter = chapter
        self._tts = tts

    async def service(self, store: AudioGenerationStore) -> None:  # noqa: D401
        start = time.perf_counter()
        with tracer.start_as_current_span("InitAudioNode") as span:
            await store.set_state({
                "chapter": self._chapter,
                "tts_generator": self._tts,
                "audio_paths": {},
            })
            span.set_attribute("braintrust.output", json.dumps({
                "segments": len(self._chapter.segments),
                "chapter_number": self._chapter.chapter_number,
            }))
            elapsed = time.perf_counter() - start
            span.set_attribute("braintrust.metrics", json.dumps({"duration_s": elapsed}))


class GenerateSegmentAudioNode(Node[AudioGenerationStore]):
    """Generate audio for one segment (runs in executor)."""

    _executor: ThreadPoolExecutor | None = None  # shared across instances
    _sem: asyncio.Semaphore | None = None

    def __init__(self, segment: TextSegment, max_concurrency: int):
        super().__init__()
        self.segment = segment
        if GenerateSegmentAudioNode._executor is None:
            GenerateSegmentAudioNode._executor = ThreadPoolExecutor(max_workers=max_concurrency)
            GenerateSegmentAudioNode._sem = asyncio.Semaphore(max_concurrency)

    async def service(self, store: AudioGenerationStore) -> None:
        start = time.perf_counter()
        async with GenerateSegmentAudioNode._sem:  # throttle
            with tracer.start_as_current_span("GenerateSegmentAudioNode") as span:
                span.set_attribute("braintrust.input", json.dumps({
                    "segment_number": self.segment.sequence_number,
                    "speaker": self.segment.speaker_name,
                }))
                state = await store.get_state()
                if not state.chapter or not state.tts_generator:
                    err = "Chapter or TTSGenerator missing in state"
                    span.set_attribute("error", err)
                    await store.set_state({"error": err})
                    raise RuntimeError(err)

                loop = asyncio.get_running_loop()
                try:
                    path: str = await loop.run_in_executor(
                        GenerateSegmentAudioNode._executor,
                        lambda: state.tts_generator.generate_audio_for_segment(
                            self.segment,
                            chapter_number=state.chapter.chapter_number,
                            chapter=state.chapter,
                        ),
                    )
                    # Update shared dict safely
                    audio_paths = dict(state.audio_paths or {})
                    audio_paths[f"segment_{self.segment.sequence_number}"] = path
                    await store.set_state({"audio_paths": audio_paths})
                    span.set_attribute("braintrust.output", json.dumps({"path": path}))
                except Exception as exc:
                    err_msg = str(exc)
                    span.set_attribute("error", err_msg)
                    await store.set_state({"error": err_msg})
                    raise
                elapsed = time.perf_counter() - start
                span.set_attribute("braintrust.metrics", json.dumps({"duration_s": elapsed}))


class StitchChapterNode(Node[AudioGenerationStore]):
    """After all segment audio is done, stitch and create playlist."""

    async def service(self, store: AudioGenerationStore) -> None:
        start = time.perf_counter()
        with tracer.start_as_current_span("StitchChapterNode") as span:
            state = await store.get_state()
            if not state.chapter or not state.tts_generator:
                err = "State incomplete before stitching"
                span.set_attribute("error", err)
                await store.set_state({"error": err})
                raise RuntimeError(err)

            stitched = state.tts_generator.stitch_chapter_audio(state.chapter, state.audio_paths or {})
            playlist = state.tts_generator.create_playlist(state.chapter, state.audio_paths or {})

            await store.set_state({
                "stitched_path": stitched,
                "playlist_path": playlist,
            })
            span.set_attribute("braintrust.output", json.dumps({
                "stitched_path": stitched,
                "playlist_path": playlist,
            }))
            elapsed = time.perf_counter() - start
            span.set_attribute("braintrust.metrics", json.dumps({"duration_s": elapsed}))


# ---------------------------------------------------------------------------
# Builder helper
# ---------------------------------------------------------------------------

def build_audio_workflow(
    chapter: Chapter,
    tts_generator: TTSGenerator,
    *,
    max_concurrency: int = 8,
) -> Workflow[AudioGenerationState, AudioGenerationStore]:
    """Return a Junjo workflow that fan-outs segment audio generation."""

    init_node = InitAudioNode(chapter, tts_generator)

    # One node per segment
    seg_nodes: List[GenerateSegmentAudioNode] = [
        GenerateSegmentAudioNode(seg, max_concurrency=max_concurrency) for seg in chapter.segments
    ]

    stitch_node = StitchChapterNode()

    edges: List[Edge] = []
    # init -> each segment node
    for n in seg_nodes:
        edges.append(Edge(tail=init_node, head=n))
        # each segment -> stitch
        edges.append(Edge(tail=n, head=stitch_node))

    graph = Graph(source=init_node, sink=stitch_node, edges=edges)

    wf = Workflow[
        AudioGenerationState, AudioGenerationStore
    ](
        name="Chapter Audio Generation Pipeline",
        graph=graph,
        store=AudioGenerationStore(initial_state=AudioGenerationState()),
    )
    return wf 