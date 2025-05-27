# Implementation Plan: Junjo-Native Chapter Parsing Pipeline (STO-27)

## Motivation

- Unlock full observability, modularity, and parallelism by implementing all parsing logic as Junjo nodes.
- Replace any remaining imperative or black-box steps with explicit, testable, and observable workflow nodes.

## Architecture Overview

- **Junjo Workflow**: The entire chapter parsing pipeline is a Junjo graph.
- **Nodes**: Each logical step is a node (chunking, prompt construction, Gemini API call, segment merging, validation, etc.).
- **State**: All intermediate and final results are stored in the Junjo state/store.
- **Parallelism**: Chunk parsing and Gemini API calls are parallelized where possible.
- **Observability**: Each node exposes traces, state, and errors for debugging and monitoring.

## Node Breakdown

1. **ChunkTextNode**
   - Input: `chapter_text`
   - Output: `chunks` (list of text chunks)
   - Logic: Split text into manageable chunks for LLM processing.
2. **PromptConstructionNode**
   - Input: `chunks`, `chapter_number`, `title`
   - Output: `prompts` (list of prompt strings)
   - Logic: Build Gemini prompts for each chunk.
3. **GeminiApiNode** (parallelized)
   - Input: `prompts`
   - Output: `raw_responses` (list of Gemini responses)
   - Logic: Make async Gemini API calls for each prompt/chunk.
4. **ParseSegmentsNode**
   - Input: `raw_responses`
   - Output: `segments` (list of parsed segments)
   - Logic: Parse and validate JSON from Gemini, flatten and renumber segments.
5. **MergeSegmentsNode**
   - Input: `segments`
   - Output: `chapter` (final Chapter object)
   - Logic: Merge all segments, validate, and build the Chapter model.
6. **ErrorHandlingNode** (optional, for retries/fallbacks)
   - Input: Any node error
   - Output: Error state, retry/fallback logic
7. **SaveResultsNode** (optional)
   - Input: `chapter`, `segments`, etc.
   - Output: Files on disk for debugging/inspection

## State Management

- State fields: `chapter_text`, `chunks`, `prompts`, `raw_responses`, `segments`, `chapter`, `error`, etc.
- Each node updates only its relevant state fields.

## Error Handling

- Each node should catch and log errors, updating the state with error info.
- Implement retry logic for Gemini API failures.
- Expose error state for observability and debugging.

## Parallelism

- Use Junjo's parallel node execution for GeminiApiNode (one per chunk).
- Ensure state merging is thread-safe and deterministic.

## Testing

- **Unit tests** for each node (input/output, error cases).
- **Integration tests** for the full workflow (end-to-end parsing, error propagation, state inspection).
- **Performance tests** for parallel chunking and Gemini calls.
- **Observability tests**: Confirm traces and state are visible in Junjo tools.

## Documentation

- Update docs to describe the new Junjo-native architecture, node breakdown, and observability features.

---

**Next Steps:**

1. Scaffold all nodes and state fields in the workflow module.
2. Implement and test each node in order (chunking → prompt → Gemini → parse/merge → save).
3. Add error handling and observability hooks.
4. Write and run tests for each node and the full graph.
5. Update documentation and API references.
