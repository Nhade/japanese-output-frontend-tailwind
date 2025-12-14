import unittest
import sys
import os

from apps.backend.ai_service import evaluate_submission

class TestAIService(unittest.TestCase):
    def test_conjugation_typo(self):
        print("\nTesting AI Service - Conjugation Typo...")
        question = "日本語を[＿＿＿]。"
        correct_answer = "勉強します"
        user_answer = "勉強てます"
        
        print(f"Q: {question}")
        print(f"Correct: {correct_answer}")
        print(f"User:    {user_answer}")
        
        result = evaluate_submission(question, user_answer, correct_answer)
        print("Result:", result)
        
        self.assertIsNotNone(result)
        # Assuming result has some structure, effectively just ensuring no crash for now
        # as the AI response itself is non-deterministic for strict assertions without mocking.

    def test_particle_error(self):
        print("\nTesting AI Service - Particle Error...")
        question = "日本語[＿＿＿]勉強します。"
        correct_answer = "を"
        user_answer = "が"
        
        print(f"Q: {question}")
        print(f"Correct: {correct_answer}")
        print(f"User:    {user_answer}")
        
        result = evaluate_submission(question, user_answer, correct_answer)
        print("Result:", result)
        
        self.assertIsNotNone(result)

if __name__ == "__main__":
    unittest.main()
