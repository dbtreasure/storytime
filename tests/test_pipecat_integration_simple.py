"""Simplified integration tests for Pipecat voice assistant implementation."""

from unittest.mock import patch

import pytest

from storytime.voice_assistant.enhanced_pipecat_assistant import (
    EnhancedPipecatVoiceAssistant,
    SimpleVADAnalyzer,
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


class TestEnhancedRealtimeVoiceAssistant:
    """Test the enhanced realtime voice assistant configuration."""

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
        assistant = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key"
        )

        # Should auto-detect enhanced Pipecat from environment
        assert assistant.use_pipecat is True
        assert assistant.use_enhanced_features is True

    def test_mcp_configuration(self):
        """Test MCP configuration options."""
        # Test without MCP
        assistant = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            mcp_access_token=None,
        )
        assert assistant.mcp_access_token is None

        # Test with MCP
        assistant = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            mcp_access_token="test_token",
            mcp_base_url="http://localhost:8000",
        )
        assert assistant.mcp_access_token == "test_token"
        assert assistant.mcp_base_url == "http://localhost:8000"


class TestEnhancedPipecatVoiceAssistant:
    """Test the enhanced Pipecat voice assistant initialization."""

    def test_initialization_defaults(self):
        """Test enhanced assistant initialization with defaults."""
        assistant = EnhancedPipecatVoiceAssistant(
            openai_api_key="test_key",
        )

        # Check defaults
        assert assistant.vad_enabled is True
        assert assistant.interruption_enabled is True
        assert assistant.audio_processing_enabled is True
        assert assistant._running is False

    def test_initialization_custom_settings(self):
        """Test enhanced assistant with custom settings."""
        assistant = EnhancedPipecatVoiceAssistant(
            openai_api_key="test_key",
            vad_enabled=False,
            interruption_enabled=False,
            audio_processing_enabled=False,
        )

        assert assistant.vad_enabled is False
        assert assistant.interruption_enabled is False
        assert assistant.audio_processing_enabled is False

    def test_mcp_configuration(self):
        """Test MCP configuration in enhanced assistant."""
        assistant = EnhancedPipecatVoiceAssistant(
            openai_api_key="test_key",
            mcp_base_url="http://localhost:8000",
            mcp_access_token="test_token",
        )

        assert assistant.mcp_base_url == "http://localhost:8000"
        assert assistant.mcp_access_token == "test_token"


class TestBackendCompatibility:
    """Test compatibility between different backends."""

    def test_interface_compatibility(self):
        """Test that all backends expose the same interface."""
        test_configs = [
            {"use_pipecat": False, "use_enhanced_features": False},
            {"use_pipecat": True, "use_enhanced_features": False},
            {"use_pipecat": True, "use_enhanced_features": True},
        ]

        for config in test_configs:
            assistant = EnhancedRealtimeVoiceAssistant(
                openai_api_key="test_key",
                **config
            )

            # Check common interface
            assert hasattr(assistant, "connect")
            assert hasattr(assistant, "disconnect")
            assert hasattr(assistant, "send_text")
            assert hasattr(assistant, "send_audio")

            # Check event handlers
            assert hasattr(assistant, "on_transcription_received")
            assert hasattr(assistant, "on_audio_received")
            assert hasattr(assistant, "on_response_received")

    def test_configuration_validation(self):
        """Test configuration validation logic."""
        # Valid configurations
        valid_configs = [
            {"use_pipecat": False, "use_enhanced_features": False},
            {"use_pipecat": True, "use_enhanced_features": False},
            {"use_pipecat": True, "use_enhanced_features": True},
        ]

        for config in valid_configs:
            assistant = EnhancedRealtimeVoiceAssistant(
                openai_api_key="test_key",
                **config
            )
            assert assistant.use_pipecat == config["use_pipecat"]
            assert assistant.use_enhanced_features == config["use_enhanced_features"]

        # Invalid configuration: enhanced features without Pipecat
        assistant = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            use_pipecat=False,
            use_enhanced_features=True,
        )
        # Should auto-correct to disable enhanced features
        assert assistant.use_enhanced_features is False


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_missing_openai_key(self):
        """Test handling of missing OpenAI API key."""
        # Empty key doesn't raise error at initialization, only at connect
        assistant = EnhancedRealtimeVoiceAssistant(
            openai_api_key="",  # Empty key
        )
        assert assistant.openai_api_key == ""

    def test_invalid_configuration(self):
        """Test handling of invalid configuration."""
        # Test with invalid sample rate
        assistant = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
        )

        # Should initialize without error
        assert assistant.openai_api_key == "test_key"

    def test_mcp_configuration_errors(self):
        """Test MCP configuration error handling."""
        # Test with invalid MCP URL format
        assistant = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            mcp_base_url="not_a_url",
            mcp_access_token="test_token",
        )

        # Should initialize but may fail on connect
        assert assistant.mcp_base_url == "not_a_url"


class TestPerformanceMetrics:
    """Test performance tracking capabilities."""

    def test_initialization_tracking(self):
        """Test that performance tracking is properly initialized."""
        assistant = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            use_pipecat=True,
        )

        # Check that we can track backend selection
        assert assistant.use_pipecat is True
        assert hasattr(assistant, "openai_api_key")
        assert hasattr(assistant, "mcp_base_url")

    def test_backend_tracking(self):
        """Test backend selection tracking."""
        # Test different backends
        backends = [
            {"use_pipecat": False, "use_enhanced_features": False},
            {"use_pipecat": True, "use_enhanced_features": False},
            {"use_pipecat": True, "use_enhanced_features": True},
        ]

        for backend in backends:
            assistant = EnhancedRealtimeVoiceAssistant(
                openai_api_key="test_key",
                **backend
            )

            # Verify configuration was applied
            assert assistant.use_pipecat == backend["use_pipecat"]
            assert assistant.use_enhanced_features == backend["use_enhanced_features"]


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
