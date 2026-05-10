import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import importlib

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

import ai_core

class TestLLMSwitch(unittest.TestCase):

    # Env vars that, if set in a developer's local .env, would leak into the
    # ai_core registry and steer the dispatcher away from whichever provider
    # the test thinks it's exercising. Cleared in setUp for a hermetic env.
    _AI_CORE_ENV_KEYS = (
        "LLM_PROVIDER", "MODEL_NAME", "API_BASE_URL", "API_KEY",
        "QUALITY_PROVIDER", "QUALITY_MODEL", "QUALITY_API_BASE_URL",
        "QUALITY_API_KEY", "QUALITY_MAX_TOKENS",
        "BALANCED_PROVIDER", "BALANCED_MODEL", "BALANCED_API_BASE_URL",
        "BALANCED_API_KEY", "BALANCED_MAX_TOKENS",
        "FAST_PROVIDER", "FAST_MODEL", "FAST_API_BASE_URL",
        "FAST_API_KEY", "FAST_MAX_TOKENS",
        "GROQ_API_KEY", "GROQ_API_BASE_URL",
    )

    def setUp(self):
        # Save original env, then pin every var ai_core looks at to an
        # empty string. ai_core calls load_dotenv() at module body time, and
        # with the default override=False it would *re-populate* any var we
        # left unset from the developer's local .env — quietly steering the
        # dispatcher to the wrong provider. Setting to "" keeps the keys
        # present in os.environ so load_dotenv treats them as already set
        # and skips them.
        self.original_env = dict(os.environ)
        for key in self._AI_CORE_ENV_KEYS:
            os.environ[key] = ""

    def tearDown(self):
        # Restore env
        os.environ.clear()
        os.environ.update(self.original_env)
        # Reload ai_core to restore state
        importlib.reload(ai_core)

    @patch('ai_core.requests.post')
    def test_ollama_provider(self, mock_post):
        """Test default Ollama provider uses requests"""
        # Set Env
        os.environ['LLM_PROVIDER'] = 'ollama'
        os.environ['API_BASE_URL'] = 'http://localhost:11434'
        importlib.reload(ai_core)

        # Mock Response
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "Ollama Reply"}}
        mock_post.return_value = mock_response

        # Call
        response = ai_core.query_llm([{"role": "user", "content": "hello"}])

        # Verify
        self.assertEqual(response, "Ollama Reply")
        mock_post.assert_called()
        args, kwargs = mock_post.call_args
        self.assertIn("localhost", args[0])

    @patch('openai.OpenAI')
    def test_openai_provider(self, mock_openai_cls):
        """Test OpenAI provider uses OpenAI client"""
        # Set Env — clear Groq vars to prevent safeguard client from being created
        os.environ['LLM_PROVIDER'] = 'openai'
        os.environ['API_KEY'] = 'sk-test'
        os.environ['MODEL_NAME'] = 'gpt-4o'
        os.environ['API_BASE_URL'] = 'https://api.groq.com/openai/v1'
        os.environ['GROQ_API_KEY'] = ''
        os.environ['GROQ_API_BASE_URL'] = ''

        # Reload so the module re-imports openai.OpenAI (now mocked) and
        # rebuilds MODEL_REGISTRY from the test env.
        importlib.reload(ai_core)

        # The module no longer keeps an eagerly-initialized openai_client;
        # the OpenAI client is created lazily inside _openai_client(cfg) on
        # first dispatch. Wire up the mock to return a stub client whose
        # chat.completions.create yields a known response.
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "OpenAI Reply"
        mock_client.chat.completions.create.return_value = mock_completion

        # Call — default tier (BALANCED) falls back to the legacy env config,
        # which is openai/gpt-4o with the api_key + base_url set above.
        response = ai_core.query_llm([{"role": "user", "content": "hello"}])

        # Verify
        self.assertEqual(response, "OpenAI Reply")
        mock_client.chat.completions.create.assert_called()

        # Check Base URL passed to client constructor (only one OpenAI() call
        # since Groq is cleared and the per-tier cache deduplicates).
        mock_openai_cls.assert_called_with(api_key='sk-test', base_url='https://api.groq.com/openai/v1')

if __name__ == '__main__':
    unittest.main()
