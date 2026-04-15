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

    def setUp(self):
        # Save original env
        self.original_env = dict(os.environ)

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

        # Reload to trigger client init with new env vars
        importlib.reload(ai_core)

        # Access the client instance assigned to the module
        mock_client = ai_core.openai_client
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = "OpenAI Reply"
        mock_client.chat.completions.create.return_value = mock_completion

        # Call
        response = ai_core.query_llm([{"role": "user", "content": "hello"}])

        # Verify
        self.assertEqual(response, "OpenAI Reply")
        mock_client.chat.completions.create.assert_called()

        # Check Base URL passed to client constructor (only one OpenAI() call since Groq is cleared)
        mock_openai_cls.assert_called_with(api_key='sk-test', base_url='https://api.groq.com/openai/v1')

if __name__ == '__main__':
    unittest.main()
