import os
import json
import requests
from enum import Enum
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Users should set API_BASE_URL to the root of their Ollama instance (e.g. http://localhost:11434)
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:11434").rstrip("/")
if BASE_URL.endswith("/v1"):
    BASE_URL = BASE_URL[:-3]

API_KEY = os.getenv("API_KEY", "ollama")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-oss:120b")
# Allow longer timeout for cold start
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "120"))

# Define Error Types
class ErrorType(str, Enum):
    NONE = "none"               # Perfect
    TYPO = "typo"               # Kana/Kanji mistake -1
    VOCAB = "vocab"             # Wrong word choice -2
    PARTICLE = "particle"       # Wrong particle -5
    CONJUGATION = "conjugation" # Wrong conjugation -10
    UNNATURAL = "unnatural"     # Contextually weird -10
    OTHER = "other"             # Other -3

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
    Call Server LLM (Ollama API) to evaluate the submission.
    Uses native /api/chat endpoint via requests to avoid issues with /v1/chat/completions.
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

    Respond STRICTLY in JSON format with two keys. Do NOT output any "thinking" or conversational text.
    
    Example Output:
    {{
        "error_type": "conjugation",
        "reasoning": "動詞「食べます」的否定形應該是「食べません」，而不是「食べくない」。"
    }}
    """

    user_prompt = f"""
    Question: {question}
    Correct Answer: {correct_answer}
    User Answer: {user_answer}
    """

    url = f"{BASE_URL}/api/chat"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=AI_TIMEOUT)
        response.raise_for_status()
        
        # Parse Ollama response
        data = response.json()
        
        content = data.get("message", {}).get("content", "")
        if not content:
             # Fallback for other structures (e.g. if 'response' is used instead of 'message')
             content = data.get("response", "")
        
        # Helper to strip markdown code blocks
        if "```" in content:
            # removing ```json ... ``` or just ``` ... ```
            import re
            content = re.sub(r'^```json\s*', '', content, flags=re.MULTILINE)
            content = re.sub(r'^```\s*', '', content, flags=re.MULTILINE)
            content = re.sub(r'\s*```$', '', content, flags=re.MULTILINE)
        
        # Parse nested JSON in content
        try:
            result_json = json.loads(content)
        except json.JSONDecodeError:
            # Fallback: Try to find JSON structure in the text
            import re
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                try:
                    result_json = json.loads(match.group(0))
                except json.JSONDecodeError:
                    raise # Still failed
            else:
                raise # No JSON found

        error_type_str = result_json.get("error_type", "other").lower()
        reasoning = result_json.get("reasoning", "No feedback provided")
        
        # Normalize error type
        try:
            error_type_enum = ErrorType(error_type_str)
        except ValueError:
            error_type_enum = ErrorType.OTHER
                
    except (json.JSONDecodeError, Exception) as e:
        print(f"Failed to parse AI response JSON. Error: {e}")
        return {
            "is_correct": False,
            "score": 0,
            "error_type": "unknown",
            "feedback": "AI 回應格式錯誤",
            "deduction": 0
        }

    # Calculate score (Max 100)
    deduction = calculate_score(error_type_enum)
    final_score = max(0, 100 + deduction)

    return {
        "is_correct": error_type_enum == ErrorType.NONE,
        "score": final_score,
        "error_type": error_type_enum.value,
        "feedback": reasoning,
        "deduction": deduction
    }

def get_detailed_feedback(question: str, user_answer: str, correct_answer: str) -> str:
    """
    Ask AI for a detailed grammatical explanation.
    """
    system_prompt = f"""
    You are a helpful Japanese language teacher.
    The user has answered a Japanese grammar question incorrectly (or partially incorrectly).
    
    Provide a detailed explanation in Traditional Chinese (繁體中文).
    - Analyze the user's mistake.
    - Explain the grammar point involved in the correct answer.
    - Provide 1-2 example sentences using the correct grammar.
    
    Keep the tone encouraging. Use Markdown formatting (bullet points, bold text) for readability.
    """

    user_prompt = f"""
    Question: {question}
    Correct Answer: {correct_answer}
    User Answer: {user_answer}
    """

    url = f"{BASE_URL}/api/chat"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=AI_TIMEOUT)
        response.raise_for_status()
        
        # Parse Ollama response
        data = response.json()
        content = data.get("message", {}).get("content", "")
        if not content:
             content = data.get("response", "")
        
        return content

    except Exception as e:
        print(f"Failed to get detailed feedback. Error: {e}")
        return "抱歉，目前無法取得詳細解說。"
