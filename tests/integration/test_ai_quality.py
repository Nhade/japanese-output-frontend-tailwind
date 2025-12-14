import unittest
import os
from apps.backend.ai_service import evaluate_submission

# Skip this test if not running explicitly, to save money/time
@unittest.skipIf(os.environ.get("TEST_AI") != "1", "Skipping AI Quality test")
class TestAIQuality(unittest.TestCase):
    
    def test_detects_typo(self):
        """AI should correctly identify a typo."""
        result = evaluate_submission(
            question="日本語を[＿＿＿]。",
            user_answer="勉強てます", # Typo: 'te' instead of 'shi'
            correct_answer="勉強します"
        )
        print(f"\nTypo Check: {result}")
        # We assert the AI actually classified it correctly
        self.assertEqual(result['error_type'], 'typo')
        self.assertTrue(result['score'] < 100)

    def test_detects_particle_error(self):
        """AI should correctly identify a particle error."""
        result = evaluate_submission(
            question="日本語[＿＿＿]勉強します。",
            user_answer="が", # Wrong particle
            correct_answer="を"
        )
        print(f"\nParticle Check: {result}")
        self.assertIn(result['error_type'], ['particle', 'vocab']) # AI might waver between these
        self.assertTrue(result['score'] <= 95)

    def test_allows_correct_answer(self):
        """AI should give 100% for a correct answer."""
        result = evaluate_submission(
            question="日本語を[＿＿＿]。",
            user_answer="勉強します",
            correct_answer="勉強します"
        )
        print(f"\nCorrect Check: {result}")
        self.assertEqual(result['error_type'], 'none')
        self.assertEqual(result['score'], 100)

if __name__ == "__main__":
    unittest.main()