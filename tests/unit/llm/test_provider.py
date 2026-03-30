"""Tests for LLM provider protocol and configuration.

This module tests the base protocol definitions in labclaw.llm.provider
to ensure 100% branch coverage of the Protocol abstract methods.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from labclaw.llm.provider import LLMConfig, LLMProvider

if TYPE_CHECKING:
    pass


class TestLLMConfig:
    """Tests for LLMConfig Pydantic model."""

    def test_default_values(self) -> None:
        """Test LLMConfig default values."""
        config = LLMConfig()

        assert config.provider == "anthropic"
        assert config.model == "claude-sonnet-4-6"
        assert config.api_key_env == "ANTHROPIC_API_KEY"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.fallback_provider is None

    def test_custom_values(self) -> None:
        """Test LLMConfig with custom values."""
        config = LLMConfig(
            provider="openai",
            model="gpt-4o",
            api_key_env="OPENAI_API_KEY",
            temperature=0.5,
            max_tokens=2048,
            fallback_provider="anthropic",
        )

        assert config.provider == "openai"
        assert config.model == "gpt-4o"
        assert config.api_key_env == "OPENAI_API_KEY"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048
        assert config.fallback_provider == "anthropic"

    def test_partial_custom_values(self) -> None:
        """Test LLMConfig with some custom and some default values."""
        config = LLMConfig(provider="fireworks", temperature=0.9)

        assert config.provider == "fireworks"
        assert config.temperature == 0.9
        # Defaults should still apply
        assert config.model == "claude-sonnet-4-6"
        assert config.api_key_env == "ANTHROPIC_API_KEY"


class TestLLMProviderProtocol:
    """Tests for LLMProvider Protocol runtime checkable behavior.

    These tests ensure the Protocol's abstract method definitions (using ...)
    are exercised for branch coverage.
    """

    def test_protocol_is_runtime_checkable(self) -> None:
        """Test that LLMProvider is a runtime-checkable protocol."""

        # This verifies the @runtime_checkable decorator is applied
        # by checking that isinstance() works (would raise TypeError otherwise)
        class DummyProvider:
            async def complete(
                self,
                prompt: str,
                *,
                system: str = "",
                temperature: float = 0.7,
                max_tokens: int = 2048,
            ) -> str:
                return ""

            async def complete_structured(
                self,
                prompt: str,
                *,
                system: str = "",
                response_model: type[BaseModel],
                temperature: float = 0.7,
            ) -> BaseModel:
                return BaseModel.construct()

            @property
            def model_name(self) -> str:
                return "test-model"

        provider = DummyProvider()
        assert isinstance(provider, LLMProvider)

    def test_invalid_implementation_isinstance_check(self) -> None:
        """Test that an invalid implementation fails isinstance check."""

        class InvalidProvider:
            # Missing complete_structured and model_name
            async def complete(
                self,
                prompt: str,
                *,
                system: str = "",
                temperature: float = 0.7,
                max_tokens: int = 2048,
            ) -> str:
                return "test"

        provider = InvalidProvider()
        assert not isinstance(provider, LLMProvider)

    def test_partial_implementation_isinstance_check(self) -> None:
        """Test that a partial implementation fails isinstance check."""

        class PartialProvider:
            # Has complete but missing complete_structured
            async def complete(
                self,
                prompt: str,
                *,
                system: str = "",
                temperature: float = 0.7,
                max_tokens: int = 2048,
            ) -> str:
                return "test"

            @property
            def model_name(self) -> str:
                return "test-model"

        provider = PartialProvider()
        assert not isinstance(provider, LLMProvider)

    def test_missing_property_isinstance_check(self) -> None:
        """Test that implementation missing model_name property fails check."""

        class NoPropertyProvider:
            async def complete(
                self,
                prompt: str,
                *,
                system: str = "",
                temperature: float = 0.7,
                max_tokens: int = 2048,
            ) -> str:
                return "test"

            async def complete_structured(
                self,
                prompt: str,
                *,
                system: str = "",
                response_model: type[BaseModel],
                temperature: float = 0.7,
            ) -> BaseModel:
                return BaseModel.construct()

        provider = NoPropertyProvider()
        assert not isinstance(provider, LLMProvider)


class TestLLMProviderProtocolMethodSignatures:
    """Tests to verify Protocol method signatures are correctly defined."""

    def test_complete_method_signature(self) -> None:
        """Test that complete method has correct signature in Protocol."""
        import inspect

        sig = inspect.signature(LLMProvider.complete)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "prompt" in params
        assert "system" in params
        assert "temperature" in params
        assert "max_tokens" in params

        # Check defaults
        assert sig.parameters["system"].default == ""
        assert sig.parameters["temperature"].default == 0.7
        assert sig.parameters["max_tokens"].default == 2048

    def test_complete_structured_method_signature(self) -> None:
        """Test that complete_structured method has correct signature."""
        import inspect

        sig = inspect.signature(LLMProvider.complete_structured)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "prompt" in params
        assert "system" in params
        assert "response_model" in params
        assert "temperature" in params

        # Check defaults
        assert sig.parameters["system"].default == ""
        assert sig.parameters["temperature"].default == 0.7

    def test_model_name_property_signature(self) -> None:
        """Test that model_name property has correct signature."""
        import inspect

        # Properties are descriptors, we check the fget signature
        sig = inspect.signature(LLMProvider.model_name.fget)  # type: ignore[misc]
        params = list(sig.parameters.keys())

        assert "self" in params


class TestConcreteProviderBehavior:
    """Tests using actual provider implementations with Protocol."""

    def test_openai_provider_isinstance(self) -> None:
        """Test that OpenAIProvider is an instance of LLMProvider."""
        from labclaw.llm.providers.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="test-key")
        assert isinstance(provider, LLMProvider)

    def test_fireworks_provider_isinstance(self) -> None:
        """Test that FireworksProvider is an instance of LLMProvider."""
        from labclaw.llm.providers.openai_provider import FireworksProvider

        provider = FireworksProvider(api_key="test-key")
        assert isinstance(provider, LLMProvider)

    @pytest.mark.asyncio
    async def test_protocol_method_calls_on_mock(self) -> None:
        """Test that Protocol methods can be called on mock implementations."""

        class TestResponse(BaseModel):
            value: str

        class MockProvider:
            def __init__(self) -> None:
                self.complete_mock = AsyncMock(return_value="mocked response")
                self.structured_mock = AsyncMock(return_value=TestResponse(value="test"))

            async def complete(
                self,
                prompt: str,
                *,
                system: str = "",
                temperature: float = 0.7,
                max_tokens: int = 2048,
            ) -> str:
                return await self.complete_mock(
                    prompt, system=system, temperature=temperature, max_tokens=max_tokens
                )

            async def complete_structured(
                self,
                prompt: str,
                *,
                system: str = "",
                response_model: type[BaseModel],
                temperature: float = 0.7,
            ) -> BaseModel:
                return await self.structured_mock(
                    prompt, system=system, response_model=response_model, temperature=temperature
                )

            @property
            def model_name(self) -> str:
                return "mock-model"

        provider = MockProvider()

        # Verify it's recognized as LLMProvider
        assert isinstance(provider, LLMProvider)

        # Test calling complete
        result = await provider.complete("test prompt", system="be helpful", temperature=0.5)
        assert result == "mocked response"
        provider.complete_mock.assert_awaited_once_with(
            "test prompt", system="be helpful", temperature=0.5, max_tokens=2048
        )

        # Test calling complete_structured
        class TestModel(BaseModel):
            value: str

        result2 = await provider.complete_structured(
            "test", response_model=TestResponse, temperature=0.3
        )
        assert result2.value == "test"
        provider.structured_mock.assert_awaited_once_with(
            "test", system="", response_model=TestResponse, temperature=0.3
        )
