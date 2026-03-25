"""
Tests for app.utils.retry.retry_with_backoff
"""

from unittest.mock import patch, MagicMock

import pytest

from app.utils.retry import retry_with_backoff


class TestRetrySuccessFirstAttempt:

    def test_retry_success_first_attempt(self):
        call_count = 0

        @retry_with_backoff(max_retries=3, exceptions=(ValueError,))
        def succeed_immediately():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = succeed_immediately()
        assert result == "ok"
        assert call_count == 1


class TestRetrySuccessAfterFailures:

    @patch("app.utils.retry.time.sleep")
    def test_retry_success_after_failures(self, mock_sleep):
        call_count = 0

        @retry_with_backoff(max_retries=3, initial_delay=1.0, jitter=False, exceptions=(ValueError,))
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient error")
            return "recovered"

        result = fail_then_succeed()
        assert result == "recovered"
        assert call_count == 3
        assert mock_sleep.call_count == 2


class TestRetryMaxExceeded:

    @patch("app.utils.retry.time.sleep")
    def test_retry_max_exceeded(self, mock_sleep):

        @retry_with_backoff(max_retries=2, initial_delay=0.01, jitter=False, exceptions=(ValueError,))
        def always_fail():
            raise ValueError("permanent error")

        with pytest.raises(ValueError, match="permanent error"):
            always_fail()

        # initial attempt + 2 retries = 3 calls total, 2 sleeps
        assert mock_sleep.call_count == 2


class TestExponentialBackoffTiming:

    @patch("app.utils.retry.time.sleep")
    def test_exponential_backoff_timing(self, mock_sleep):
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            initial_delay=1.0,
            backoff_factor=2.0,
            jitter=False,
            exceptions=(RuntimeError,),
        )
        def fail_three_times():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise RuntimeError("fail")
            return "ok"

        result = fail_three_times()
        assert result == "ok"

        # Delays should be 1.0, 2.0, 4.0 (without jitter)
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0]


class TestNonRetryableException:

    @patch("app.utils.retry.time.sleep")
    def test_non_retryable_exception(self, mock_sleep):
        """Exception not in the exceptions tuple should raise immediately."""

        @retry_with_backoff(max_retries=3, exceptions=(ValueError,))
        def raise_type_error():
            raise TypeError("not retryable")

        with pytest.raises(TypeError, match="not retryable"):
            raise_type_error()

        # Should not sleep at all — raised immediately
        mock_sleep.assert_not_called()
