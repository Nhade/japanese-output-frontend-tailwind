import os
import json
from openai import OpenAI
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI Client strictly for local Ollama
# We point to localhost:11434/v1 which mimics OpenAI API
client = OpenAI(
    base_url=os.getenv("API_BASE_URL", "http://localhost:11434/v1"),
    api_key=os.getenv("API_KEY", "ollama")  # Ollama requires an API key but ignores it
)

MODEL_NAME = "llama3.1:8b-instruct-q5_K_M"

# Define Error Types
class ErrorType(str, Enum):
    NONE = "none"               # Perfect
    TYPO = "typo"               # Kana/Kanji mistake -1
    VOCAB = "vocab"             # Wrong word choice -2
    PARTICLE = "particle"       # Wrong particle -5
    CONJUGATION = "conjugation" # Wrong conjugation -10
    UNNATURAL = "unnatural"     # Contextually weird -10
    OTHER = "other"             # Other -3

# Define Structured Output Schema
class EvaluationResult(BaseModel):
    error_type: ErrorType = Field(..., description="The category of the error made by the user.")
    reasoning: str = Field(..., description="A short explanation (30-50 characters) of the mistake in Traditional Chinese.")

def calculate_score(error_type: ErrorType) -> int:
    """Calculate score deduction based on error type"""
    mapping = {
        ErrorType.NONE: 0,
        ErrorType.TYPO: -1,
        ErrorType.VOCAB: -2,
        ErrorType.PARTICLE: -5,
        ErrorType.CONJUGATION: -10,
        ErrorType.UNNATURAL: -10,
        ErrorType.OTHER: -3
    }
    return mapping.get(error_type, -3)

def evaluate_submission(question: str, user_answer: str, correct_answer: str) -> dict:
    """
    Call Local LLM (Ollama) to evaluate the submission.
    """
    system_prompt = f"""
    You are a strict Japanese language teacher. 
    Analyze the user's answer based on the correct answer and the question context.
    
    Classify the error into one of these types:
    - NONE: Perfect match or semantically identical.
    - TYPO: Minor kana/kanji mistakes.
    - VOCAB: Wrong word choice but grammatically ok.
    - PARTICLE: Wrong particle.
    - CONJUGATION: Wrong verb/adjective conjugation.
    - UNNATURAL: Grammatically correct but contextually weird, or complete nonsense.
    
    Provide a concise explanation in Traditional Chinese (繁體中文), around 30-50 characters.
    """

    user_prompt = f"""
    Question: {question}
    Correct Answer: {correct_answer}
    User Answer: {user_answer}
    """

    try:
        # Check if model enables structured outputs (Ollama v0.1.26+ supports response_format)
        # We try to use the parse method which is cleaner.
        response = client.beta.chat.completions.parse(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=EvaluationResult,
            temperature=0.1,
        )

        result = response.choices[0].message.parsed
        
        # Calculate score (Max 100)
        deduction = calculate_score(result.error_type)
        final_score = max(0, 100 + deduction)

        return {
            "is_correct": result.error_type == ErrorType.NONE,
            "score": final_score,
            "error_type": result.error_type.value,
            "feedback": result.reasoning,
            "deduction": deduction
        }

    except Exception as e:
        print(f"AI Evaluation Error: {e}")
        # Fallback mechanism if AI fails
        return {
            "is_correct": False,
            "score": 0,
            "error_type": "unknown",
            "feedback": "暫時無法進行 AI 解析",
            "deduction": 0
        }
