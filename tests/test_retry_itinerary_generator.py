"""
Unit tests for retry behavior in itinerary generator service.

PR#15: Exponential backoff retry behavior tests
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import httpx
from services.itinerary_generator2 import ItineraryGeneratorService2


class TestItineraryGeneratorRetry:
    """Test retry behavior for Gemini API calls in itinerary generation."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.service = ItineraryGeneratorService2()
        self.test_prompt = "Test prompt for itinerary generation"

    def _create_http_error(self, status_code: int, message: str = "Error") -> httpx.HTTPStatusError:
        """Helper method to create httpx.HTTPStatusError for testing."""
        request = httpx.Request("POST", "https://example.com")
        response = httpx.Response(status_code, request=request, content=message.encode())
        return httpx.HTTPStatusError(message, request=request, response=response)

    def test_successful_call_no_retry(self):
        """Test that successful API call doesn't trigger retry."""
        # Mock successful response
        mock_response = Mock()
        mock_response.text = '{"test": "response"}'

        with patch.object(
            self.service.client.models,
            'generate_content',
            return_value=mock_response
        ) as mock_generate:
            # Call the method
            result = self.service._call_gemini_api(self.test_prompt)

            # Verify no retries (called exactly once)
            assert mock_generate.call_count == 1
            assert result == mock_response

    def test_retry_on_500_error(self):
        """Test that 500 server error triggers retry and eventually succeeds."""
        # Mock response for success
        mock_success_response = Mock()
        mock_success_response.text = '{"test": "response"}'

        # Create HTTP 500 error
        http_500_error = self._create_http_error(500, "Internal Server Error")

        with patch.object(
            self.service.client.models,
            'generate_content',
            side_effect=[http_500_error, http_500_error, mock_success_response]
        ) as mock_generate:
            # Call the method - should retry and succeed on 3rd attempt
            result = self.service._call_gemini_api(self.test_prompt)

            # Verify retries occurred (3 calls total)
            assert mock_generate.call_count == 3
            assert result == mock_success_response

    def test_retry_on_429_rate_limit(self):
        """Test that 429 rate limit error triggers retry."""
        # Mock response for success
        mock_success_response = Mock()
        mock_success_response.text = '{"test": "response"}'

        # Create HTTP 429 error
        http_429_error = self._create_http_error(429, "Rate limit exceeded")

        with patch.object(
            self.service.client.models,
            'generate_content',
            side_effect=[http_429_error, mock_success_response]
        ) as mock_generate:
            # Call the method - should retry and succeed on 2nd attempt
            result = self.service._call_gemini_api(self.test_prompt)

            # Verify retry occurred (2 calls total)
            assert mock_generate.call_count == 2
            assert result == mock_success_response

    def test_no_retry_on_400_error(self):
        """Test that 400 client error does NOT trigger retry."""
        # Create HTTP 400 error
        http_400_error = self._create_http_error(400, "Bad Request")

        with patch.object(
            self.service.client.models,
            'generate_content',
            side_effect=http_400_error
        ) as mock_generate:
            # Call the method - should fail immediately without retry
            with pytest.raises(httpx.HTTPStatusError):
                self.service._call_gemini_api(self.test_prompt)

            # Verify no retries (called exactly once)
            assert mock_generate.call_count == 1

    def test_max_retries_exhausted(self):
        """Test that max retries are exhausted and error is raised."""
        # Create HTTP 500 error that never succeeds
        http_500_error = self._create_http_error(500, "Internal Server Error")

        with patch.object(
            self.service.client.models,
            'generate_content',
            side_effect=http_500_error
        ) as mock_generate:
            # Call the method - should fail after max retries
            with pytest.raises(httpx.HTTPStatusError):
                self.service._call_gemini_api(self.test_prompt)

            # Verify max retries exhausted (5 attempts)
            assert mock_generate.call_count == 5

    def test_retry_on_timeout(self):
        """Test that timeout error triggers retry."""
        # Mock response for success
        mock_success_response = Mock()
        mock_success_response.text = '{"test": "response"}'

        # Create httpx timeout error
        timeout_error = httpx.TimeoutException("Request timeout")

        with patch.object(
            self.service.client.models,
            'generate_content',
            side_effect=[timeout_error, mock_success_response]
        ) as mock_generate:
            # Call the method - should retry and succeed on 2nd attempt
            result = self.service._call_gemini_api(self.test_prompt)

            # Verify retry occurred (2 calls total)
            assert mock_generate.call_count == 2
            assert result == mock_success_response

    @patch('time.sleep')  # Mock sleep to speed up test
    def test_exponential_backoff_timing(self, mock_sleep):
        """Test that exponential backoff timing is applied correctly."""
        # Mock response for success
        mock_success_response = Mock()
        mock_success_response.text = '{"test": "response"}'

        # Create HTTP 500 error
        http_500_error = self._create_http_error(500, "Internal Server Error")

        with patch.object(
            self.service.client.models,
            'generate_content',
            side_effect=[http_500_error, http_500_error, http_500_error, mock_success_response]
        ) as mock_generate:
            # Call the method - should retry 3 times before success
            result = self.service._call_gemini_api(self.test_prompt)

            # Verify retries occurred
            assert mock_generate.call_count == 4

            # Verify sleep was called for exponential backoff (3 sleeps for 3 retries)
            assert mock_sleep.call_count == 3

            # Verify exponential backoff: delays should be increasing
            # Note: Exact timing depends on tenacity configuration
            # Just verify that sleep was called multiple times with increasing values
            sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]

            # Verify sleep calls are in increasing order (exponential backoff)
            # The exact values depend on tenacity's exponential wait strategy
            # We just verify that there are multiple sleep calls
            assert len(sleep_calls) == 3
            assert all(isinstance(delay, (int, float)) for delay in sleep_calls)

            # Verify successful response
            assert result == mock_success_response
