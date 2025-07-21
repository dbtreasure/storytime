"""Performance tests for Pipecat voice assistant implementation."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from storytime.voice_assistant.enhanced_realtime_client import EnhancedRealtimeVoiceAssistant


class TestPerformanceBenchmarks:
    """Performance benchmarks for different backends."""

    def test_initialization_performance(self):
        """Test initialization speed of different backends."""

        # Test Original backend
        start_time = time.time()
        assistant_original = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            use_pipecat=False,
        )
        original_time = time.time() - start_time

        # Test Basic Pipecat backend
        start_time = time.time()
        assistant_pipecat = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            use_pipecat=True,
            use_enhanced_features=False,
        )
        pipecat_time = time.time() - start_time

        # Test Enhanced Pipecat backend
        start_time = time.time()
        assistant_enhanced = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            use_pipecat=True,
            use_enhanced_features=True,
        )
        enhanced_time = time.time() - start_time

        # Log performance results
        print("\nInitialization Performance:")
        print(f"  Original: {original_time:.4f}s")
        print(f"  Basic Pipecat: {pipecat_time:.4f}s")
        print(f"  Enhanced Pipecat: {enhanced_time:.4f}s")

        # All should initialize quickly (under 1 second)
        assert original_time < 1.0
        assert pipecat_time < 1.0
        assert enhanced_time < 1.0

    def test_memory_usage_comparison(self):
        """Test memory usage of different backends."""
        import os

        import psutil

        process = psutil.Process(os.getpid())

        # Baseline memory
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create original assistant
        assistant_original = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            use_pipecat=False,
        )
        original_memory = process.memory_info().rss / 1024 / 1024  # MB
        del assistant_original

        # Create Pipecat assistant
        assistant_pipecat = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            use_pipecat=True,
            use_enhanced_features=False,
        )
        pipecat_memory = process.memory_info().rss / 1024 / 1024  # MB
        del assistant_pipecat

        # Create enhanced assistant
        assistant_enhanced = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            use_pipecat=True,
            use_enhanced_features=True,
        )
        enhanced_memory = process.memory_info().rss / 1024 / 1024  # MB
        del assistant_enhanced

        print("\nMemory Usage:")
        print(f"  Baseline: {baseline_memory:.1f} MB")
        print(f"  Original: {original_memory:.1f} MB (+{original_memory - baseline_memory:.1f} MB)")
        print(f"  Basic Pipecat: {pipecat_memory:.1f} MB (+{pipecat_memory - baseline_memory:.1f} MB)")
        print(f"  Enhanced Pipecat: {enhanced_memory:.1f} MB (+{enhanced_memory - baseline_memory:.1f} MB)")

        # Memory usage should be reasonable (all under 100MB additional)
        assert (original_memory - baseline_memory) < 100
        assert (pipecat_memory - baseline_memory) < 100
        assert (enhanced_memory - baseline_memory) < 100

    def test_configuration_selection_speed(self):
        """Test speed of backend selection logic."""
        import os

        # Test different environment configurations
        test_cases = [
            ({"USE_PIPECAT_BACKEND": "false"}, False, False),
            ({"USE_PIPECAT_BACKEND": "true"}, True, False),
            ({"USE_PIPECAT_BACKEND": "true", "USE_ENHANCED_FEATURES": "true"}, True, True),
        ]

        for env_vars, expected_pipecat, expected_enhanced in test_cases:
            # Set environment variables
            for key, value in env_vars.items():
                os.environ[key] = value

            start_time = time.time()
            assistant = EnhancedRealtimeVoiceAssistant(
                openai_api_key="test_key"
            )
            selection_time = time.time() - start_time

            # Verify correct selection
            assert assistant.use_pipecat == expected_pipecat
            assert assistant.use_enhanced_features == expected_enhanced

            # Should be very fast (under 10ms)
            assert selection_time < 0.01

            # Clean up environment
            for key in env_vars.keys():
                if key in os.environ:
                    del os.environ[key]

    @pytest.mark.asyncio
    async def test_mock_connection_speed(self):
        """Test connection speed with mocked services."""

        # Test original backend connection speed
        assistant_original = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            use_pipecat=False,
        )

        # Mock WebSocket connection
        mock_ws = AsyncMock()

        with pytest.MonkeyPatch().context() as m:
            m.setattr("websockets.connect", AsyncMock(return_value=mock_ws))

            start_time = time.time()
            await assistant_original.connect()
            original_connect_time = time.time() - start_time

        await assistant_original.disconnect()

        # Test enhanced backend connection speed
        assistant_enhanced = EnhancedRealtimeVoiceAssistant(
            openai_api_key="test_key",
            use_pipecat=True,
            use_enhanced_features=True,
        )

        # Mock enhanced assistant
        mock_enhanced = MagicMock()
        mock_enhanced.connect = AsyncMock()

        with pytest.MonkeyPatch().context() as m:
            m.setattr(
                "storytime.voice_assistant.enhanced_pipecat_assistant.EnhancedPipecatVoiceAssistant",
                lambda **kwargs: mock_enhanced
            )

            start_time = time.time()
            await assistant_enhanced.connect()
            enhanced_connect_time = time.time() - start_time

        await assistant_enhanced.disconnect()

        print("\nConnection Performance (mocked):")
        print(f"  Original: {original_connect_time:.4f}s")
        print(f"  Enhanced Pipecat: {enhanced_connect_time:.4f}s")

        # Both should connect quickly when mocked
        assert original_connect_time < 1.0
        assert enhanced_connect_time < 1.0


class TestScalabilityMetrics:
    """Test scalability and resource usage."""

    def test_multiple_assistant_creation(self):
        """Test creating multiple assistants simultaneously."""

        assistants = []
        start_time = time.time()

        # Create 10 assistants
        for i in range(10):
            assistant = EnhancedRealtimeVoiceAssistant(
                openai_api_key=f"test_key_{i}",
                use_pipecat=(i % 2 == 0),  # Alternate between backends
                use_enhanced_features=(i % 3 == 0),  # Every third has enhanced features
            )
            assistants.append(assistant)

        creation_time = time.time() - start_time

        # Verify all assistants were created
        assert len(assistants) == 10

        # Check configuration diversity
        pipecat_count = sum(1 for a in assistants if a.use_pipecat)
        enhanced_count = sum(1 for a in assistants if a.use_enhanced_features)

        assert pipecat_count == 5  # Half should use Pipecat
        assert enhanced_count > 0  # Some should use enhanced features

        print("\nScalability Test:")
        print(f"  Created 10 assistants in {creation_time:.4f}s")
        print(f"  Average: {creation_time/10:.4f}s per assistant")
        print(f"  Pipecat backends: {pipecat_count}/10")
        print(f"  Enhanced backends: {enhanced_count}/10")

        # Should create quickly even with multiple instances
        assert creation_time < 5.0  # All 10 in under 5 seconds

    def test_configuration_memory_impact(self):
        """Test memory impact of different configurations."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        baseline = process.memory_info().rss

        # Create assistants with different configurations
        configs = [
            {"use_pipecat": False, "use_enhanced_features": False},
            {"use_pipecat": True, "use_enhanced_features": False},
            {"use_pipecat": True, "use_enhanced_features": True},
        ]

        memory_usage = {}
        assistants = []

        for i, config in enumerate(configs):
            assistant = EnhancedRealtimeVoiceAssistant(
                openai_api_key=f"test_key_{i}",
                **config
            )
            assistants.append(assistant)

            current_memory = process.memory_info().rss
            config_name = f"{'Pipecat' if config['use_pipecat'] else 'Original'}"
            if config.get('use_enhanced_features'):
                config_name += " Enhanced"

            memory_usage[config_name] = (current_memory - baseline) / 1024 / 1024  # MB

        print("\nMemory Impact by Configuration:")
        for config, usage in memory_usage.items():
            print(f"  {config}: +{usage:.1f} MB")

        # Clean up
        del assistants

        # Memory usage should be reasonable for all configurations
        for usage in memory_usage.values():
            assert usage < 50.0  # Under 50MB per assistant


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])  # -s to show print statements
