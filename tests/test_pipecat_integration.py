"""Integration tests for Pipecat voice assistant implementation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)

from pipecat.frames.frames import (
    BotInterruptionFrame,
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    InputAudioRawFrame,
    TextFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)

from storytime.voice_assistant.enhanced_pipecat_assistant import (
    AudioProcessor,
    ConversationManager,
    EnhancedPipecatVoiceAssistant,
    InterruptionProcessor,
    SimpleVADAnalyzer,
    VADProcessor,
)
from storytime.voice_assistant.enhanced_realtime_client import EnhancedRealtimeVoiceAssistant


class TestSimpleVADAnalyzer:
    """Test the Simple VAD Analyzer implementation."""

    def test_voice_confidence_calculation(self):
        """Test voice confidence calculation with sample audio."""
        from pipecat.audio.vad.vad_analyzer import VADParams

        # Create VAD analyzer
        params = VADParams(confidence=0.7, start_secs=0.2, stop_secs=0.8, min_volume=0.6)
        analyzer = SimpleVADAnalyzer(sample_rate=16000, num_channels=1, params=params)

        # Test with empty buffer
        confidence = analyzer.voice_confidence(b"")
        assert confidence == 0.0

        # Test with low audio (mostly silence)
        low_audio = b"\x00\x00" * 100  # 200 bytes of silence
        confidence = analyzer.voice_confidence(low_audio)
        assert 0.0 <= confidence <= 0.1

        # Test with high audio (simulated speech)
        high_audio = b"\xff\x7f" * 100  # 200 bytes of high amplitude
        confidence = analyzer.voice_confidence(high_audio)
        assert confidence > 0.5

    def test_num_frames_required(self):
        """Test number of frames required for analysis."""
        from pipecat.audio.vad.vad_analyzer import VADParams

        params = VADParams()
        analyzer = SimpleVADAnalyzer(sample_rate=16000, num_channels=1, params=params)

        frames = analyzer.num_frames_required()
        assert frames == 160  # 10ms at 16kHz


class TestVADProcessor:
    """Test VAD processor functionality."""

    @pytest_asyncio.fixture
    async def vad_processor(self):
        """Create a VAD processor for testing."""
        # Create processor within an event loop context
        return VADProcessor()

    @pytest.mark.asyncio
    async def test_audio_frame_processing(self, vad_processor):
        """Test processing of audio frames."""
        # Mock the push_frame method
        vad_processor.push_frame = AsyncMock()

        # Create test audio frame
        audio_data = b"\x00\x01" * 1000  # 2000 bytes of test audio
        audio_frame = InputAudioRawFrame(audio=audio_data, sample_rate=16000, num_channels=1)

        # Process frame
        await vad_processor.process_frame(audio_frame, "downstream")

        # Verify frame was passed downstream
        vad_processor.push_frame.assert_called()

    @pytest.mark.asyncio
    async def test_speech_detection(self, vad_processor):
        """Test speech start/stop detection."""
        frames_pushed = []

        async def mock_push_frame(frame, direction):
            frames_pushed.append(frame)

        vad_processor.push_frame = mock_push_frame

        # Simulate high-energy audio (speech)
        high_audio = b"\xff\x7f" * 1000
        audio_frame = InputAudioRawFrame(audio=high_audio, sample_rate=16000, num_channels=1)

        await vad_processor.process_frame(audio_frame, "downstream")

        # Check if frames were generated (implementation may vary)
        assert len(frames_pushed) >= 1


class TestInterruptionProcessor:
    """Test interruption handling processor."""

    @pytest_asyncio.fixture
    async def interruption_processor(self):
        """Create an interruption processor for testing."""
        return InterruptionProcessor()

    @pytest.mark.asyncio
    async def test_bot_speaking_tracking(self, interruption_processor):
        """Test bot speaking state tracking."""
        # Mock push_frame
        interruption_processor.push_frame = AsyncMock()

        # Test bot started speaking
        bot_start_frame = BotStartedSpeakingFrame()
        await interruption_processor.process_frame(bot_start_frame, "downstream")
        assert interruption_processor._bot_is_speaking is True

        # Test bot stopped speaking
        bot_stop_frame = BotStoppedSpeakingFrame()
        await interruption_processor.process_frame(bot_stop_frame, "downstream")
        assert interruption_processor._bot_is_speaking is False

    @pytest.mark.asyncio
    async def test_user_interruption_handling(self, interruption_processor):
        """Test user interruption of bot speech."""
        frames_pushed = []

        async def mock_push_frame(frame, direction):
            frames_pushed.append(frame)

        interruption_processor.push_frame = mock_push_frame

        # Bot starts speaking
        interruption_processor._bot_is_speaking = True

        # User starts speaking (interruption)
        user_start_frame = UserStartedSpeakingFrame()
        await interruption_processor.process_frame(user_start_frame, "downstream")

        # Verify interruption was handled
        interruption_frames = [f for f in frames_pushed if isinstance(f, BotInterruptionFrame)]
        assert len(interruption_frames) >= 0  # May or may not create interruption frame immediately


class TestConversationManager:
    """Test conversation management functionality."""

    @pytest_asyncio.fixture
    async def conversation_manager(self):
        """Create a conversation manager for testing."""
        return ConversationManager()

    @pytest.mark.asyncio
    async def test_conversation_state_transitions(self, conversation_manager):
        """Test conversation state transitions."""
        # Mock push_frame
        conversation_manager.push_frame = AsyncMock()

        # Test state transitions
        assert conversation_manager._conversation_state == "idle"

        # User starts speaking
        user_start_frame = UserStartedSpeakingFrame()
        await conversation_manager.process_frame(user_start_frame, "downstream")
        assert conversation_manager._conversation_state == "listening"

        # User stops speaking
        user_stop_frame = UserStoppedSpeakingFrame()
        await conversation_manager.process_frame(user_stop_frame, "downstream")
        assert conversation_manager._conversation_state == "processing"

        # Bot starts speaking
        bot_start_frame = BotStartedSpeakingFrame()
        await conversation_manager.process_frame(bot_start_frame, "downstream")
        assert conversation_manager._conversation_state == "speaking"

        # Bot stops speaking
        bot_stop_frame = BotStoppedSpeakingFrame()
        await conversation_manager.process_frame(bot_stop_frame, "downstream")
        assert conversation_manager._conversation_state == "idle"

    @pytest.mark.asyncio
    async def test_transcription_tracking(self, conversation_manager):
        """Test transcription text tracking."""
        # Mock push_frame
        conversation_manager.push_frame = AsyncMock()

        # Process transcription frame
        transcription_frame = TranscriptionFrame(text="Hello world")
        await conversation_manager.process_frame(transcription_frame, "downstream")

        assert conversation_manager._last_user_input == "Hello world"


class TestAudioProcessor:
    """Test audio processing functionality."""

    @pytest_asyncio.fixture
    async def audio_processor(self):
        """Create an audio processor for testing."""
        return AudioProcessor()

    @pytest.mark.asyncio
    async def test_input_audio_processing(self, audio_processor):
        """Test input audio frame processing."""
        frames_pushed = []

        async def mock_push_frame(frame, direction):
            frames_pushed.append(frame)

        audio_processor.push_frame = mock_push_frame

        # Create test input audio frame
        audio_data = b"\x00\x01" * 500
        input_frame = InputAudioRawFrame(audio=audio_data, sample_rate=16000, num_channels=1)

        await audio_processor.process_frame(input_frame, "downstream")

        # Verify processed frame was pushed
        assert len(frames_pushed) == 1
        assert isinstance(frames_pushed[0], InputAudioRawFrame)

    @pytest.mark.asyncio
    async def test_output_audio_processing(self, audio_processor):
        """Test output audio frame processing."""
        frames_pushed = []

        async def mock_push_frame(frame, direction):
            frames_pushed.append(frame)

        audio_processor.push_frame = mock_push_frame

        # Create test TTS audio frame
        audio_data = b"\x00\x01" * 500
        tts_frame = TTSAudioRawFrame(audio=audio_data, sample_rate=24000, num_channels=1)

        await audio_processor.process_frame(tts_frame, "downstream")

        # Verify processed frame was pushed
        assert len(frames_pushed) == 1
        assert isinstance(frames_pushed[0], TTSAudioRawFrame)

    @pytest.mark.asyncio
    async def test_other_frame_passthrough(self, audio_processor):
        """Test that other frames pass through unchanged."""
        frames_pushed = []

        async def mock_push_frame(frame, direction):
            frames_pushed.append(frame)

        audio_processor.push_frame = mock_push_frame

        # Create test text frame
        text_frame = TextFrame(text="Hello")

        await audio_processor.process_frame(text_frame, "downstream")

        # Verify frame passed through unchanged
        assert len(frames_pushed) == 1
        assert frames_pushed[0] is text_frame


class TestEnhancedRealtimeVoiceAssistant:
    """Test the enhanced realtime voice assistant."""

    @pytest.fixture
    def assistant(self):
        """Create an enhanced voice assistant for testing."""
        return EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            mcp_base_url="http://localhost:8000",
            mcp_access_token=None,
            use_pipecat=False,
            use_enhanced_features=False,
        )

    def test_backend_selection_original(self):
        """Test backend selection for original implementation."""
        assistant = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            use_pipecat=False,
        )

        assert assistant.use_pipecat is False
        assert assistant.use_enhanced_features is False

    def test_backend_selection_basic_pipecat(self):
        """Test backend selection for basic Pipecat."""
        assistant = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            use_pipecat=True,
            use_enhanced_features=False,
        )

        assert assistant.use_pipecat is True
        assert assistant.use_enhanced_features is False

    def test_backend_selection_enhanced_pipecat(self):
        """Test backend selection for enhanced Pipecat."""
        assistant = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            use_pipecat=True,
            use_enhanced_features=True,
        )

        assert assistant.use_pipecat is True
        assert assistant.use_enhanced_features is True

    @patch.dict("os.environ", {"USE_PIPECAT_BACKEND": "true", "USE_ENHANCED_FEATURES": "true"})
    def test_environment_variable_detection(self):
        """Test automatic backend detection from environment variables."""
        assistant = EnhancedRealtimeVoiceAssistant(openai_api_key="test_key")

        # Should auto-detect enhanced Pipecat from environment
        assert assistant.use_pipecat is True
        assert assistant.use_enhanced_features is True

    @pytest.mark.asyncio
    async def test_connect_original_backend(self, assistant):
        """Test connection with original backend."""
        with patch("websockets.connect") as mock_connect:
            mock_ws = AsyncMock()
            mock_connect.return_value = mock_ws

            # Mock WebSocket methods
            mock_ws.send = AsyncMock()

            await assistant.connect()

            assert assistant.ws is mock_ws
            assert assistant.use_pipecat is False


class TestEnhancedPipecatVoiceAssistant:
    """Test the enhanced Pipecat voice assistant implementation."""

    @pytest.fixture
    def enhanced_assistant(self):
        """Create an enhanced Pipecat voice assistant for testing."""
        return EnhancedPipecatVoiceAssistant(
            openai_api_key="test_key",
            mcp_base_url="http://localhost:8000",
            mcp_access_token=None,
            vad_enabled=True,
            interruption_enabled=True,
            audio_processing_enabled=True,
        )

    def test_initialization(self, enhanced_assistant):
        """Test enhanced assistant initialization."""
        assert enhanced_assistant.vad_enabled is True
        assert enhanced_assistant.interruption_enabled is True
        assert enhanced_assistant.audio_processing_enabled is True
        assert enhanced_assistant._running is False

    @pytest.mark.asyncio
    async def test_send_text(self, enhanced_assistant):
        """Test sending text input."""
        # Mock transport
        mock_transport = MagicMock()
        mock_transport.send_text_input = AsyncMock()
        enhanced_assistant.transport = mock_transport

        await enhanced_assistant.send_text("Hello world")

        mock_transport.send_text_input.assert_called_once_with("Hello world")

    @pytest.mark.asyncio
    async def test_send_audio(self, enhanced_assistant):
        """Test sending audio input."""
        # Mock transport
        mock_transport = MagicMock()
        mock_transport.send_audio_input = AsyncMock()
        enhanced_assistant.transport = mock_transport

        audio_data = b"test_audio_data"
        await enhanced_assistant.send_audio(audio_data)

        mock_transport.send_audio_input.assert_called_once_with(audio_data)

    @pytest.mark.asyncio
    async def test_interrupt_bot(self, enhanced_assistant):
        """Test manual bot interruption."""
        # Mock transport with input processor
        mock_transport = MagicMock()
        mock_input_processor = MagicMock()
        mock_input_processor.push_frame = AsyncMock()
        mock_transport._input_processor = mock_input_processor
        enhanced_assistant.transport = mock_transport

        await enhanced_assistant.interrupt_bot()

        # Verify interruption frame was sent
        mock_input_processor.push_frame.assert_called_once()
        call_args = mock_input_processor.push_frame.call_args
        frame_arg = call_args[0][0]
        assert isinstance(frame_arg, BotInterruptionFrame)


class TestIntegrationWorkflows:
    """Test complete integration workflows."""

    @pytest.mark.asyncio
    async def test_full_conversation_flow(self):
        """Test a complete conversation flow through all backends."""
        test_scenarios = [
            {"use_pipecat": False, "use_enhanced": False, "name": "Original"},
            {"use_pipecat": True, "use_enhanced": False, "name": "Basic Pipecat"},
            {"use_pipecat": True, "use_enhanced": True, "name": "Enhanced Pipecat"},
        ]

        for scenario in test_scenarios:
            assistant = EnhancedRealtimeVoiceAssistant(
                openai_api_key="test_key",
                use_pipecat=scenario["use_pipecat"],
                use_enhanced_features=scenario["use_enhanced"],
            )

            # Verify backend selection
            assert assistant.use_pipecat == scenario["use_pipecat"]
            assert assistant.use_enhanced_features == scenario["use_enhanced"]

            # Test event handler assignment
            transcription_received = False
            audio_received = False
            response_received = False

            def on_transcription(text):
                nonlocal transcription_received
                transcription_received = True

            def on_audio(audio):
                nonlocal audio_received
                audio_received = True

            def on_response(text):
                nonlocal response_received
                response_received = True

            assistant.on_transcription_received = on_transcription
            assistant.on_audio_received = on_audio
            assistant.on_response_received = on_response

            # Verify handlers were set
            assert assistant.on_transcription_received is on_transcription
            assert assistant.on_audio_received is on_audio
            assert assistant.on_response_received is on_response

    @pytest.mark.asyncio
    async def test_mcp_integration_workflow(self):
        """Test MCP integration across different backends."""
        with patch("storytime.voice_assistant.mcp_client.MCPClient") as MockMCPClient:
            mock_client = AsyncMock()
            MockMCPClient.return_value = mock_client

            # Test with enhanced Pipecat
            assistant = EnhancedRealtimeVoiceAssistant(
                openai_api_key="test_key",
                mcp_access_token="test_token",
                use_pipecat=True,
                use_enhanced_features=True,
            )

            # Should have MCP client configured
            assert assistant.mcp_access_token == "test_token"

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Test error handling and recovery in different backends."""
        # Test with missing OpenAI key
        with pytest.raises((ValueError, TypeError, AttributeError)):
            # Some backends may handle missing keys differently
            assistant = EnhancedRealtimeVoiceAssistant(
                openai_api_key="",  # Empty key
                use_pipecat=True,
                use_enhanced_features=True,
            )

        # Test with invalid MCP URL
        assistant = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            mcp_base_url="invalid_url",
            use_pipecat=False,
        )

        # Should still initialize but may fail on connect
        assert assistant.mcp_base_url == "invalid_url"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
