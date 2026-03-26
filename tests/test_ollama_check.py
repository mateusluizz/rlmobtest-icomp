"""Tests for Ollama availability checks and pipeline guard.

Verifies that:
- check_ollama_server() correctly detects server reachability
- check_ollama_model() correctly detects model installation
- `rlmobtest pipeline` refuses to start when Ollama is offline
"""

import json
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from rlmobtest.cli import app
from rlmobtest.constants.llm import DEFAULT_LLM_MODEL, DEFAULT_OLLAMA_BASE_URL
from rlmobtest.utils.ollama import check_ollama_model, check_ollama_server

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_response(body: bytes = b"Ollama is running"):
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _tags_response(model_names: list[str]) -> MagicMock:
    payload = {"models": [{"name": name} for name in model_names]}
    return _fake_response(json.dumps(payload).encode())


# ---------------------------------------------------------------------------
# check_ollama_server()
# ---------------------------------------------------------------------------


class TestCheckOllamaServer:
    def test_returns_true_when_server_responds(self):
        with patch("rlmobtest.utils.ollama.urllib.request.urlopen") as mock:
            mock.return_value = _fake_response()
            assert check_ollama_server() is True

    def test_returns_false_when_server_is_down(self):
        with patch("rlmobtest.utils.ollama.urllib.request.urlopen") as mock:
            mock.side_effect = urllib.error.URLError("Connection refused")
            assert check_ollama_server() is False

    def test_returns_false_on_timeout(self):
        with patch("rlmobtest.utils.ollama.urllib.request.urlopen") as mock:
            mock.side_effect = TimeoutError("timed out")
            assert check_ollama_server() is False

    def test_returns_false_on_http_error(self):
        with patch("rlmobtest.utils.ollama.urllib.request.urlopen") as mock:
            mock.side_effect = urllib.error.HTTPError(
                url=DEFAULT_OLLAMA_BASE_URL,
                code=503,
                msg="Service Unavailable",
                hdrs={},  # type: ignore[arg-type]
                fp=None,
            )
            assert check_ollama_server() is False

    def test_returns_false_on_unexpected_exception(self):
        with patch("rlmobtest.utils.ollama.urllib.request.urlopen") as mock:
            mock.side_effect = RuntimeError("unexpected")
            assert check_ollama_server() is False

    def test_uses_configured_base_url(self):
        """Confirms the function hits the URL passed as argument."""
        custom_url = "http://custom-host:11434"
        with patch("rlmobtest.utils.ollama.urllib.request.urlopen") as mock:
            mock.return_value = _fake_response()
            check_ollama_server(base_url=custom_url)
            called_url = mock.call_args[0][0]
            assert called_url == custom_url


# ---------------------------------------------------------------------------
# check_ollama_model()
# ---------------------------------------------------------------------------


class TestCheckOllamaModel:
    def test_returns_true_when_model_is_installed(self):
        with patch("rlmobtest.utils.ollama.urllib.request.urlopen") as mock:
            mock.return_value = _tags_response([DEFAULT_LLM_MODEL, "llama3:8b"])
            assert check_ollama_model() is True

    def test_returns_false_when_model_is_not_installed(self):
        with patch("rlmobtest.utils.ollama.urllib.request.urlopen") as mock:
            mock.return_value = _tags_response(["llama3:8b", "mistral:7b"])
            assert check_ollama_model() is False

    def test_returns_false_when_model_list_is_empty(self):
        with patch("rlmobtest.utils.ollama.urllib.request.urlopen") as mock:
            mock.return_value = _tags_response([])
            assert check_ollama_model() is False

    def test_returns_false_when_server_is_down(self):
        with patch("rlmobtest.utils.ollama.urllib.request.urlopen") as mock:
            mock.side_effect = urllib.error.URLError("Connection refused")
            assert check_ollama_model() is False

    def test_returns_false_on_malformed_json(self):
        with patch("rlmobtest.utils.ollama.urllib.request.urlopen") as mock:
            mock.return_value = _fake_response(b"not json")
            assert check_ollama_model() is False

    def test_model_name_must_match_exactly(self):
        """Partial name (e.g. 'gemma3' without tag) must not pass."""
        partial = DEFAULT_LLM_MODEL.split(":")[0]
        with patch("rlmobtest.utils.ollama.urllib.request.urlopen") as mock:
            mock.return_value = _tags_response([partial])
            assert check_ollama_model() is False

    def test_queries_api_tags_endpoint(self):
        """Must hit /api/tags, not the root."""
        with patch("rlmobtest.utils.ollama.urllib.request.urlopen") as mock:
            mock.return_value = _tags_response([DEFAULT_LLM_MODEL])
            check_ollama_model()
            called_url = mock.call_args[0][0]
            assert called_url.endswith("/api/tags")

    def test_custom_model_and_base_url(self):
        with patch("rlmobtest.utils.ollama.urllib.request.urlopen") as mock:
            mock.return_value = _tags_response(["custom:latest"])
            result = check_ollama_model(model="custom:latest", base_url="http://localhost:11434")
            assert result is True


# ---------------------------------------------------------------------------
# Pipeline guard: must exit early when Ollama is offline
# ---------------------------------------------------------------------------


class TestPipelineOllamaGuard:
    """Verifies that `rlmobtest pipeline` blocks startup when Ollama is down."""

    def test_pipeline_exits_when_ollama_server_is_down(self):
        """Pipeline must not start if the server is unreachable."""
        with patch("rlmobtest.cli.pipeline.check_ollama_model", return_value=False):
            result = runner.invoke(app, ["pipeline"])
        assert result.exit_code != 0, (
            "Pipeline should exit with non-zero code when Ollama is offline"
        )

    def test_pipeline_exits_when_model_is_not_installed(self):
        """Pipeline must not start if the server is up but the model is missing."""
        with patch("rlmobtest.cli.pipeline.check_ollama_model", return_value=False):
            result = runner.invoke(app, ["pipeline", "--llm-model", "nonexistent:model"])
        assert result.exit_code != 0

    def test_pipeline_shows_helpful_error_message(self):
        """Output must explain what went wrong and how to fix it."""
        with patch("rlmobtest.cli.pipeline.check_ollama_model", return_value=False):
            result = runner.invoke(app, ["pipeline"])
        assert "ollama" in result.output.lower() or "Ollama" in result.output

    def test_pipeline_proceeds_when_ollama_is_available(self):
        """When Ollama is available, pipeline must pass the guard and continue."""
        with (
            patch("rlmobtest.cli.pipeline.check_ollama_model", return_value=True),
            patch("rlmobtest.cli.pipeline.ConfRead") as mock_conf,
        ):
            # Simulate config error to stop execution right after the guard
            mock_conf.return_value.read_all_settings.side_effect = RuntimeError("stop here")
            result = runner.invoke(app, ["pipeline"])

        # Exit is due to config error, not Ollama check
        assert "Ollama" not in result.output or "indisponível" not in result.output
