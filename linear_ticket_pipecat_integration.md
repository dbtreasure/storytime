# Linear Ticket: Integrate Pipecat AI for Enhanced Voice Assistant Pipeline

## Title
Integrate Pipecat AI framework for robust voice assistant pipeline (CORE-XX)

## Description
Research has revealed that our current voice assistant implementation could benefit significantly from integrating Pipecat AI's battle-tested real-time voice interaction framework. This ticket covers refactoring our voice assistant to use Pipecat's superior audio pipeline while preserving our unique MCP server architecture.

## Problem Statement
Our current voice assistant implementation (`src/storytime/voice_assistant/`) has several limitations:
- Custom WebSocket handling that could be more robust
- Basic audio processing without sophisticated VAD or interruption handling
- Tightly coupled OpenAI Realtime API integration
- Limited transport flexibility

Pipecat AI provides production-ready solutions for these challenges with a frame-based architecture, superior audio pipeline, and multi-provider support.

## Proposed Solution
Implement a **hybrid architecture** that combines:
- **Pipecat's voice pipeline** for audio processing, transport, and real-time communication
- **Our existing MCP server** for tool orchestration and business logic
- **Custom integration layer** to bridge Pipecat frames with MCP protocol

## Technical Approach

### Phase 1: Foundation & Research (2-3 days)
- [ ] Add Pipecat AI as dependency to project
- [ ] Create proof-of-concept Pipecat pipeline with OpenAI Realtime API
- [ ] Design integration architecture between Pipecat frames and MCP tools
- [ ] Document frame-based architecture patterns for team

### Phase 2: Core Integration (3-4 days)
- [ ] Create `PipecatVoiceProcessor` that implements Pipecat's FrameProcessor interface
- [ ] Implement MCP tool bridge to convert Pipecat frames to MCP tool calls
- [ ] Refactor `realtime_client.py` to use Pipecat's OpenAI integration
- [ ] Create transport abstraction layer using Pipecat's patterns

### Phase 3: Enhanced Features (2-3 days)
- [ ] Implement sophisticated interruption handling using Pipecat's patterns
- [ ] Add Voice Activity Detection (VAD) support
- [ ] Integrate improved turn detection and conversation management
- [ ] Add audio processing pipeline with noise reduction

### Phase 4: Testing & Integration (2-3 days)
- [ ] Update existing voice assistant tests for new architecture
- [ ] Create integration tests for Pipecat-MCP bridge
- [ ] Test with MCP Inspector to ensure tool functionality preserved
- [ ] Performance testing and optimization

### Phase 5: Documentation & Deployment (1-2 days)
- [ ] Update CLAUDE.md with new voice assistant architecture
- [ ] Create migration guide for existing voice assistant code
- [ ] Update deployment configurations for new dependencies
- [ ] Create troubleshooting guide for Pipecat integration

## Key Components to Implement

### 1. MCP-Pipecat Bridge
```python
class MCPToolProcessor(FrameProcessor):
    """Bridge between Pipecat frames and MCP tool calls"""
    async def process_frame(self, frame):
        if isinstance(frame, LLMFunctionCallFrame):
            # Convert to MCP tool call
            result = await self.mcp_client.call_tool(frame.tool_name, frame.arguments)
            # Return as ToolCallResultFrame
```

### 2. Enhanced Voice Pipeline
```python
pipeline = Pipeline([
    transport.input(),                    # WebSocket/WebRTC input
    OpenAIRealtimeSTT(),                 # Pipecat's STT integration
    MCPToolProcessor(mcp_client),        # Our custom MCP bridge
    OpenAIRealtimeTTS(),                 # Pipecat's TTS integration
    transport.output(),                  # Audio output
])
```

### 3. Transport Abstraction
- Support both WebSocket and WebRTC transports
- Unified interface for different client types
- Built-in reconnection and error handling

## Success Criteria
- [ ] Voice assistant maintains all existing functionality (library search, job queries)
- [ ] Improved audio quality with VAD and interruption handling
- [ ] Better conversation flow and turn management
- [ ] MCP Inspector tests pass with new architecture
- [ ] Performance metrics show improved latency and reliability
- [ ] Deployment successfully integrates new dependencies

## Dependencies
- Pipecat AI framework (`pip install pipecat-ai`)
- Existing MCP server infrastructure
- OpenAI Realtime API access
- Current authentication system (JWT)

## Risks & Mitigations
1. **Breaking existing voice assistant functionality**
   - Mitigation: Incremental integration with feature flags
   - Keep old implementation available during transition

2. **Complex integration between Pipecat and MCP**
   - Mitigation: Create clear abstraction layer
   - Extensive testing of bridge functionality

3. **Increased dependency complexity**
   - Mitigation: Thorough documentation and testing
   - Evaluate long-term maintenance implications

## Estimated Effort
**Total: 10-15 days**
- Research & Foundation: 2-3 days
- Core Integration: 3-4 days  
- Enhanced Features: 2-3 days
- Testing & Integration: 2-3 days
- Documentation: 1-2 days

## Priority
**Medium** - Significant improvement to voice assistant capabilities, but not blocking current functionality

## Labels
- `enhancement`
- `voice-assistant`
- `architecture`
- `integration`

## Acceptance Criteria
1. Voice assistant uses Pipecat for audio pipeline while preserving MCP functionality
2. All existing MCP tools (search_library, search_job, ask_job_question) work seamlessly
3. Improved audio quality with VAD and interruption handling
4. MCP Inspector tests pass with new architecture
5. Documentation updated to reflect new architecture
6. Performance benchmarks show improvement or equivalent performance
7. Deployment pipeline successfully handles new dependencies

---

**Additional Context:**
This integration represents a strategic architectural improvement that leverages a mature, battle-tested framework while preserving our unique MCP-based tool orchestration. The hybrid approach allows us to benefit from Pipecat's sophisticated voice processing while maintaining our competitive advantage in content-aware voice interactions.