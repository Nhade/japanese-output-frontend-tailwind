import os
import json
import requests
from enum import Enum
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
API_KEY = os.getenv("API_KEY", "ollama")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-oss:120b")
AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "120"))

# Base URL handling
# If OpenAI provider, allow API_BASE_URL to override default (e.g. for Groq), otherwise None uses default.
# If Ollama, default to localhost.
raw_base_url = os.getenv("API_BASE_URL")
if LLM_PROVIDER == "openai":
    BASE_URL = raw_base_url if raw_base_url else None 
else:
    # Ollama default
    BASE_URL = raw_base_url if raw_base_url else "http://localhost:11434"
    if BASE_URL.endswith("/v1"):
        BASE_URL = BASE_URL[:-3]

# Initialize OpenAI Client if needed (lazy init is also fine, but global is easier for now)
openai_client = None
if LLM_PROVIDER == "openai":
    openai_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

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

def query_llm(messages: List[Dict[str, str]], json_mode: bool = False, temperature: float = 0.7) -> str:
    """
    Unified function to query the configured LLM provider.
    Returns the text content of the response.
    """
    if LLM_PROVIDER == "openai" and openai_client:
        try:
            response_format = {"type": "json_object"} if json_mode else {"type": "text"}
            
            completion = openai_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                response_format=response_format,
                temperature=temperature,
                timeout=AI_TIMEOUT
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API Error: {e}")
            raise e
    else:
        # Fallback to Ollama (requests)
        url = f"{BASE_URL.rstrip('/')}/api/chat"
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": MODEL_NAME,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        # Ollama 'format' param for JSON mode
        if json_mode:
            payload["format"] = "json"

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=AI_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            content = data.get("message", {}).get("content", "")
            if not content:
                content = data.get("response", "")
            return content
            
        except requests.RequestException as e:
            print(f"Ollama API Error: {e}")
            raise e

def _parse_json_safe(content: str) -> dict:
    """Helper to parse JSON from LLM response with cleanup strategies."""
    # 1. Direct try
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
        
    # 2. Cleanup markdown code blocks
    import re
    cleaned = re.sub(r'^```json\s*', '', content, flags=re.MULTILINE)
    cleaned = re.sub(r'^```\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\s*```$', '', cleaned, flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Find first { and last }
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
            
    raise ValueError(f"Could not parse JSON from content: {content[:100]}...")

def evaluate_submission(question: str, user_answer: str, correct_answer: str) -> dict:
    """
    Call Server LLM to evaluate the submission.
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

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        content = query_llm(messages, json_mode=True, temperature=0.1)
        result_json = _parse_json_safe(content)

        error_type_str = result_json.get("error_type", "other").lower()
        reasoning = result_json.get("reasoning", "No feedback provided")
        
        # Normalize error type
        try:
            error_type_enum = ErrorType(error_type_str)
        except ValueError:
            error_type_enum = ErrorType.OTHER
                
    except Exception as e:
        print(f"Failed to evaluate submission. Error: {e}")
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

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        content = query_llm(messages, json_mode=False, temperature=0.7)
        return content

    except Exception as e:
        print(f"Failed to get detailed feedback. Error: {e}")
        return "抱歉，目前無法取得詳細解說。"

def build_learner_context(profile: dict) -> dict:
    """
    Generate a short, human-readable block from the profile.
    """
    level = profile.get("level_est", "N5")
    # Retrieve weak_points, defaulting to empty list if missing/None
    weak = profile.get("weak_points", [])
    if weak is None: weak = []
    
    # Take top 2 weak points
    top_weak = weak[:2]
    
    pref = profile.get("feedback_preference", "gentle")

    focus = ", ".join(top_weak) if top_weak else "general Japanese basics"

    max_corrections = {
        "gentle": 2,
        "normal": 3,
        "strict": 5
    }.get(pref, 2)

    return {
        "summary": f"Learner profile:\n- Estimated level: {level}\n- Common weak points: {focus}\n- Feedback preference: {pref}\n- Max corrections: {max_corrections}",
        "max_corrections": max_corrections
    }

def chat_with_ai(message: str, history: list, locale: str = 'en', learner_profile: dict = None) -> dict:
    """
    Chat with the AI in Japanese.
    
    Args:
        message: The latest user message.
        history: List of dictionary {'role': 'user'|'assistant', 'content': '...'}
        locale: User's locale (e.g. 'en', 'ja', 'zh-tw').
        learner_profile: Dict containing learner stats and preferences.
        
    Returns:
        Dict with keys:
        - response: Japanese reply
        - feedback: Dict containing analysis of the user's Japanese
    """
    
    # 1. Sliding Window for History (Keep last 10 turns to save tokens)
    trimmed_history = history[-20:] if len(history) > 20 else history

    # 2. Determine Feedback Language
    if locale == 'en':
        feedback_intro = "Reply in Japanese (Natural). Feedback/Explanations MUST be in English."
        feedback_lang = "English"
    else:
        # Default to Traditional Chinese for zh-tw and ja
        feedback_intro = "Reply in Japanese (Natural). Feedback/Explanations MUST be in Traditional Chinese (繁體中文)."
        feedback_lang = "Traditional Chinese"

    # 3. Build Learner Context
    if learner_profile:
        context_data = build_learner_context(learner_profile)
        learner_context = context_data["summary"]
        max_corrections = context_data["max_corrections"]
    else:
        # Default generic context
        learner_context = "Learner profile: User is a beginner. Treat as N5 level."
        max_corrections = 2

    system_prompt = f"""
    You are a friendly and helpful Japanese language tutor.

    Your goal is to have a natural conversation with the user in Japanese,
    while providing focused, level-appropriate feedback based on their learning profile.

    {learner_context}

    Instructions:

    1. Role
    - Act as a native Japanese speaker.
    - Be polite, encouraging, and supportive.
    - Match your Japanese difficulty to the learner’s estimated level.
      - N5: short sentences, common words, です／ます form
      - N4: slightly longer sentences, simple casual allowed if user uses it
      - N3+: more natural expressions allowed

    2. Language rules
    - Your reply ("response") MUST be in Japanese only.
    - All feedback content MUST be written in {feedback_lang}.
    - {feedback_intro}

    3. Feedback rules
    - You MUST prioritize corrections related to the learner’s weak points.
    - Do NOT correct everything.
    - Focus on errors that affect clarity or sound unnatural.
    - Limit the number of corrections to AT MOST {max_corrections}.
    - If the learner’s Japanese is acceptable, keep feedback encouraging and minimal.

    4. Correction format rules
    - In each correction, quote ONLY the minimal incorrect part.
    - Use clear and simple explanations suitable for the learner’s level.

    5. Non-Japanese input handling
    - If the user writes mostly in English or Chinese:
      - Respond politely in Japanese encouraging them to try Japanese.
      - Still provide brief feedback in {feedback_lang} if possible.

    6. Output format (STRICT)
    - You MUST return a VALID JSON object.
    - DO NOT output any text outside the JSON.
    - DO NOT include markdown or explanations outside JSON.

    JSON Structure:
    {{
      "response": "Your natural Japanese reply.",
      "feedback": {{
        "overall": "Brief evaluation or encouragement (in {feedback_lang}).",
        "corrections": [
          {{
            "type": "particle | conjugation | word_choice | politeness | word_order | other",
            "original": "incorrect part only",
            "corrected": "corrected Japanese",
            "explanation": "explanation in {feedback_lang}"
          }}
        ]
      }}
    }}

    If the user's Japanese is correct or natural enough, return an empty list for "corrections".
    """

    messages = [{"role": "system", "content": system_prompt}]
    
    # Append history
    for msg in trimmed_history:
        # Sanitize role just in case
        role = "assistant" if msg.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": msg.get("content", "")})
    
    # Append current message
    messages.append({"role": "user", "content": message})

    try:
        content = query_llm(messages, json_mode=True, temperature=0.7)
        result_json = _parse_json_safe(content)

        # Validate keys
        if "response" not in result_json:
             result_json["response"] = "申し訳ありません、もう一度お願いします。"
        
        if "feedback" not in result_json:
             result_json["feedback"] = {
                 "overall": "無法取得回饋",
                 "corrections": []
             }
             
        return result_json
        
    except Exception as e:
        print(f"Chat error: {e}")
        # Fallback response
        return {
            "response": "すみません、エラーが発生しました。",
            "feedback": {
                "overall": f"AI 服務暫時無法回應 ({str(e)})",
                "corrections": []
            }
        }
