import unittest
from unittest.mock import patch, MagicMock
from apps.backend.ai_service import evaluate_submission

class TestAIService(unittest.TestCase):

    @patch('ai_core.check_safety', return_value={"violation": 0, "rationale": "test"})
    @patch('ai_core.query_llm')
    def test_typo_correction(self, mock_llm, mock_safety):
        print("\nTesting AI Service Logic (Mocked)...")

        # 1. Mock the LLM response (query_llm returns raw string)
        mock_llm.return_value = '{"error_type": "typo", "reasoning": "Fake reasoning"}'

        # 2. Run your function
        result = evaluate_submission("日本語を[＿＿＿]。", "勉強てます", "勉強します")

        # 3. Verify that your function logic handled the JSON correctly
        self.assertEqual(result['error_type'], 'typo')
        self.assertEqual(result['score'], 99) # 100 - 1 for typo

        # Verify we actually called the LLM
        mock_llm.assert_called_once()

if __name__ == "__main__":
    unittest.main()
