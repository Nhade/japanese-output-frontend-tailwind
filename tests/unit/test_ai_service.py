import unittest
from unittest.mock import patch, MagicMock
from apps.backend.ai_service import evaluate_submission

class TestAIService(unittest.TestCase):
    
    @patch('apps.backend.ai_service.requests.post')
    def test_typo_correction(self, mock_post):
        print("\nTesting AI Service Logic (Mocked)...")

        # 1. Mock the API response
        # We tell Python: "When requests.post is called, return this fake JSON"
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "content": '{"error_type": "typo", "reasoning": "Fake reasoning"}'
            }
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # 2. Run your function
        result = evaluate_submission("日本語を[＿＿＿]。", "勉強てます", "勉強します")

        # 3. Verify that your function logic handled the JSON correctly
        self.assertEqual(result['error_type'], 'typo')
        self.assertEqual(result['score'], 99) # 100 - 1 for typo
        
        # Verify we actually called the API (even though it was mocked)
        mock_post.assert_called_once()

if __name__ == "__main__":
    unittest.main()