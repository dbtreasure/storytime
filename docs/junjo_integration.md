# Junjo Integration for Chapter Parsing Pipeline

## Overview

This document describes the integration of the [Junjo](https://junjo.ai) workflow engine into the Storytime chapter parsing pipeline. The goal is to provide modular, observable, and maintainable orchestration of the parsing process using Junjo's graph-based state management and tracing features.

---

## Motivation

- **Observability**: Gain full traceability and state introspection for each step in the parsing pipeline.
- **Modularity**: Encapsulate each logical step (text loading, character analysis, parsing, saving) as a reusable node.
- **Testability**: Enable unit and integration testing of each pipeline stage.
- **Extensibility**: Make it easy to add, remove, or reorder steps in the workflow.
- **Production Readiness**: Leverage Junjo's OpenTelemetry integration for distributed tracing in production.

---

## Architecture

### Junjo Concepts Used

- **State**: All workflow data is managed in a Pydantic model (`ChapterParsingState`), subclassing `junjo.BaseState`.
- **Store**: State is accessed and updated via a `ChapterParsingStore` (subclass of `junjo.BaseStore`).
- **Node**: Each pipeline step is a subclass of `junjo.Node`, implementing an async `service` method.
- **Edge**: Directed edges (`junjo.Edge`) connect nodes, defining the pipeline's flow.
- **Graph**: The pipeline is composed as a `junjo.Graph` with explicit source, sink, and edges.
- **Workflow**: The graph and store are wrapped in a `junjo.Workflow`, which manages execution and state.

### Pipeline Structure

```
LoadTextNode → AnalyzeCharactersNode → ParseSegmentsNode → SaveResultsNode
```

#### Node Responsibilities

- **LoadTextNode**: Loads chapter text from a file or state.
- **AnalyzeCharactersNode**: Analyzes characters using the existing `CharacterAnalyzer`.
- **ParseSegmentsNode**: Parses chapter text into segments and builds the `Chapter` object using Junjo-native logic. The old `ChapterParser` is no longer used.
- **SaveResultsNode**: Saves results (text, segments, character catalogue) to disk for debugging/observability.

#### State Model (`ChapterParsingState`)

- `chapter_text`: str | None
- `file_path`: str | None
- `chapter_number`: int | None
- `title`: str | None
- `character_catalogue`: CharacterCatalogue | None
- `segments`: list[TextSegment] | None
- `chapter`: Chapter | None

#### Store (`ChapterParsingStore`)

- Inherits from `junjo.BaseStore[ChapterParsingState]`
- Provides async state management and update helpers

#### Graph & Workflow

- **Graph**: Created with `source`, `sink`, and a list of `Edge` objects (not tuples)
- **Workflow**: Instantiated as `Workflow[ChapterParsingState, ChapterParsingStore]`
- **Runner**: Async `main()` function for local testing, sets initial state and runs the workflow

---

## Observability & Tracing

- All node executions are automatically traced by Junjo (OpenTelemetry spans)
- State transitions are observable and can be exported for debugging
- The workflow is ready for integration with distributed tracing backends (e.g., Jaeger, Zipkin)
- Errors and exceptions are captured at each node, improving debuggability

---

## Example Usage

```python
from storytime.workflows.chapter_parsing import workflow
import asyncio

async def run_pipeline():
    await workflow.store.set_state({
        "file_path": "tests/fixtures/chapter_1.txt",
        "chapter_number": 1,
        "title": "Anna Pavlovna's Salon",
    })
    await workflow.execute()
    state = await workflow.get_state_json()
    print("Final workflow state:", state)

if __name__ == "__main__":
    asyncio.run(run_pipeline())
```

---

## Mapping to Junjo Docs

- **Node**: [junjo.Node](https://python-api.junjo.ai/api#junjo.Node)
- **Edge**: [junjo.Edge](https://python-api.junjo.ai/api#junjo.Edge)
- **Graph**: [junjo.Graph](https://python-api.junjo.ai/api#junjo.Graph)
- **Workflow**: [junjo.Workflow](https://python-api.junjo.ai/api#junjo.Workflow)
- **State/Store**: [junjo.BaseState](https://python-api.junjo.ai/api#junjo.BaseState), [junjo.BaseStore](https://python-api.junjo.ai/api#junjo.BaseStore)

---

## Next Steps

- **Testing**: Add unit and integration tests for each node and the full workflow
- **API/CLI Integration**: Refactor API endpoints and CLI commands to use the new workflow
- **Observability**: Optionally enable OpenTelemetry backends for production tracing
- **Documentation**: Update project docs and READMEs to reference the new workflow

---

## References

- [Junjo Official Docs](https://junjo.ai)
- [Junjo Python API Reference](https://python-api.junjo.ai/api)

> **Migration Note:** The legacy ChapterParser pipeline has been fully replaced by the Junjo workflow. All chapter parsing, both in the API and CLI, is now handled by Junjo nodes for full observability and modularity.
