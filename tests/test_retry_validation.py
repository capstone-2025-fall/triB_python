"""
Unit tests for retry behavior in validation service.

PR#16: Exponential backoff retry behavior tests for rule validation
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import httpx
from services.validators import _call_gemini_validation
from google.genai import types


class TestValidationRetry:
    """Test retry behavior for Gemini API calls in rule validation."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_client = Mock()
        self.test_model = "gemini-2.5-pro"
        self.test_prompt = "Test prompt for validation"
        self.test_temperature = 0.3

    def _create_http_error(self, status_code: int, message: str = "Error") -> httpx.HTTPStatusError:
        """Helper method to create httpx.HTTPStatusError for testing."""
        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(status_code, request=request, content=message.encode())
        return httpx.HTTPStatusError(message, request=request, response=response)

    def test_successful_validation_no_retry(self):
        """Test that successful API call doesn't trigger retry."""
        # Mock successful response
        mock_response = Mock()
        mock_response.text = '{"rule_results": []}'

        self.mock_client.models.generate_content = Mock(return_value=mock_response)

        # Call the method
        result = _call_gemini_validation(
            client=self.mock_client,
            model=self.test_model,
            prompt=self.test_prompt,
            temperature=self.test_temperature
        )

        # Verify no retries (called exactly once)
        assert self.mock_client.models.generate_content.call_count == 1
        assert result == mock_response

    def test_retry_on_500_error(self):
        """Test that 500 server error triggers retry and eventually succeeds."""
        # Mock response for success
        mock_success_response = Mock()
        mock_success_response.text = '{"rule_results": []}'

        # Create HTTP 500 error
        http_500_error = self._create_http_error(500, "Internal Server Error")

        self.mock_client.models.generate_content = Mock(
            side_effect=[http_500_error, http_500_error, mock_success_response]
        )

        # Call the method - should retry and succeed on 3rd attempt
        result = _call_gemini_validation(
            client=self.mock_client,
            model=self.test_model,
            prompt=self.test_prompt,
            temperature=self.test_temperature
        )

        # Verify retries occurred (3 calls total)
        assert self.mock_client.models.generate_content.call_count == 3
        assert result == mock_success_response

    def test_retry_on_429_rate_limit(self):
        """Test that 429 rate limit error triggers retry."""
        # Mock response for success
        mock_success_response = Mock()
        mock_success_response.text = '{"rule_results": []}'

        # Create HTTP 429 error
        http_429_error = self._create_http_error(429, "Rate limit exceeded")

        self.mock_client.models.generate_content = Mock(
            side_effect=[http_429_error, mock_success_response]
        )

        # Call the method - should retry and succeed on 2nd attempt
        result = _call_gemini_validation(
            client=self.mock_client,
            model=self.test_model,
            prompt=self.test_prompt,
            temperature=self.test_temperature
        )

        # Verify retry occurred (2 calls total)
        assert self.mock_client.models.generate_content.call_count == 2
        assert result == mock_success_response

    def test_no_retry_on_400_error(self):
        """Test that 400 client error does NOT trigger retry."""
        # Create HTTP 400 error
        http_400_error = self._create_http_error(400, "Bad Request")

        self.mock_client.models.generate_content = Mock(
            side_effect=http_400_error
        )

        # Call the method - should fail immediately without retry
        with pytest.raises(httpx.HTTPStatusError):
            _call_gemini_validation(
                client=self.mock_client,
                model=self.test_model,
                prompt=self.test_prompt,
                temperature=self.test_temperature
            )

        # Verify no retries (called exactly once)
        assert self.mock_client.models.generate_content.call_count == 1

    def test_max_retries_exhausted(self):
        """Test that max retries are exhausted and error is raised."""
        # Create HTTP 500 error that never succeeds
        http_500_error = self._create_http_error(500, "Internal Server Error")

        self.mock_client.models.generate_content = Mock(
            side_effect=http_500_error
        )

        # Call the method - should fail after max retries
        with pytest.raises(httpx.HTTPStatusError):
            _call_gemini_validation(
                client=self.mock_client,
                model=self.test_model,
                prompt=self.test_prompt,
                temperature=self.test_temperature
            )

        # Verify max retries exhausted (3 attempts for validation)
        assert self.mock_client.models.generate_content.call_count == 3

    def test_retry_on_timeout(self):
        """Test that timeout error triggers retry."""
        # Mock response for success
        mock_success_response = Mock()
        mock_success_response.text = '{"rule_results": []}'

        # Create httpx timeout error
        timeout_error = httpx.TimeoutException("Request timeout")

        self.mock_client.models.generate_content = Mock(
            side_effect=[timeout_error, mock_success_response]
        )

        # Call the method - should retry and succeed on 2nd attempt
        result = _call_gemini_validation(
            client=self.mock_client,
            model=self.test_model,
            prompt=self.test_prompt,
            temperature=self.test_temperature
        )

        # Verify retry occurred (2 calls total)
        assert self.mock_client.models.generate_content.call_count == 2
        assert result == mock_success_response

    @patch('time.sleep')  # Mock sleep to speed up test
    def test_exponential_backoff_timing(self, mock_sleep):
        """Test that exponential backoff timing is applied correctly."""
        # Mock response for success
        mock_success_response = Mock()
        mock_success_response.text = '{"rule_results": []}'

        # Create HTTP 500 error
        http_500_error = self._create_http_error(500, "Internal Server Error")

        self.mock_client.models.generate_content = Mock(
            side_effect=[http_500_error, http_500_error, mock_success_response]
        )

        # Call the method - should retry 2 times before success
        result = _call_gemini_validation(
            client=self.mock_client,
            model=self.test_model,
            prompt=self.test_prompt,
            temperature=self.test_temperature
        )

        # Verify retries occurred
        assert self.mock_client.models.generate_content.call_count == 3

        # Verify sleep was called for exponential backoff (2 sleeps for 2 retries)
        assert mock_sleep.call_count == 2

        # Verify exponential backoff: delays should be increasing
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]

        # Verify sleep calls exist and are numeric
        assert len(sleep_calls) == 2
        assert all(isinstance(delay, (int, float)) for delay in sleep_calls)

        # Verify successful response
        assert result == mock_success_response
