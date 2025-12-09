import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_service import evaluate_submission

def test_ai():
    print("Testing AI Service with Local Ollama...")
    
    # Test Case 1: Typography Error
    question_1 = "日本語を[＿＿＿]。"
    correct_answer_1 = "勉強します"
    user_answer_1 = "勉強てます" # conjugation error or typp? "shimasu" vs "temasu" -> probably conjugation or nonsense
    
    print(f"\nTest 1 (Conjugation/Typo):")
    print(f"Q: {question_1}")
    print(f"Correct: {correct_answer_1}")
    print(f"User:    {user_answer_1}")
    
    result = evaluate_submission(question_1, user_answer_1, correct_answer_1)
    print("Result:", result)
    
    # Test Case 2: Particle Error
    question_2 = "日本語[＿＿＿]勉強します。"
    user_answer_2 = "が" # Wrong particle
    correct_answer_2 = "を"
    print(f"\nTest 2 (Particle):")
    print(f"Q: {question_2}")
    print(f"Correct: {correct_answer_2}")
    print(f"User:    {user_answer_2}")
    
    result2 = evaluate_submission(question_2, user_answer_2, correct_answer_2)
    print("Result:", result2)

if __name__ == "__main__":
    test_ai()
