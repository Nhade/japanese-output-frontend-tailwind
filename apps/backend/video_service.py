"""
Video import service — fetches YouTube transcripts, generates cloze exercises.

Public API:
  - create_video_tables(conn)   — ensure tables exist
  - import_video(url, db_path)  — full pipeline: fetch metadata + transcript → generate exercises
"""
import json
import os
import random
import re
import sqlite3
import tempfile
import uuid
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import requests
from janome.tokenizer import Tokenizer

from translation_service import translate_text

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def create_video_tables(conn: sqlite3.Connection):
    """Create video-related tables if they don't exist."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            external_id TEXT,
            url TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            channel_name TEXT,
            category TEXT,
            publish_date TEXT,
            thumbnail_url TEXT,
            transcript_json TEXT,
            duration_seconds INTEGER,
            language TEXT DEFAULT 'ja',
            status TEXT DEFAULT 'unprocessed',
            created_timestamp TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS video_exercises (
            exercise_id TEXT PRIMARY KEY,
            video_id TEXT NOT NULL REFERENCES videos(video_id),
            full_sentence TEXT NOT NULL,
            question_sentence TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            part_of_speech TEXT,
            jlpt_level INTEGER,
            hint_chinese TEXT,
            context_timestamp REAL,
            created_timestamp TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS video_answer_log (
            log_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id),
            exercise_id TEXT NOT NULL,
            video_id TEXT NOT NULL REFERENCES videos(video_id),
            exercise_type TEXT NOT NULL,
            user_answer TEXT,
            is_correct INTEGER,
            score INTEGER DEFAULT 0,
            feedback TEXT,
            answered_timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()


# ---------------------------------------------------------------------------
# YouTube helpers
# ---------------------------------------------------------------------------

def parse_youtube_url(url: str) -> str:
    """Extract video ID from a YouTube URL. Raises ValueError if not parseable."""
    parsed = urlparse(url)
    host = parsed.hostname or ""

    # Standard: youtube.com/watch?v=ID
    if "youtube.com" in host:
        qs = parse_qs(parsed.query)
        video_id = qs.get("v", [None])[0]
        if video_id:
            return video_id
        # Embed: youtube.com/embed/ID
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/embed/")[1].split("/")[0].split("?")[0]

    # Short: youtu.be/ID
    if "youtu.be" in host:
        return parsed.path.lstrip("/").split("/")[0].split("?")[0]

    raise ValueError(f"Could not extract video ID from URL: {url}")


def fetch_youtube_metadata(video_id: str) -> dict:
    """Fetch basic metadata via YouTube oEmbed (no API key required)."""
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        resp = requests.get(oembed_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {
            "title": data.get("title", "Untitled"),
            "channel_name": data.get("author_name", ""),
            "thumbnail_url": data.get("thumbnail_url", ""),
        }
    except Exception as e:
        print(f"oEmbed fetch failed: {e}")
        return {"title": "Untitled", "channel_name": "", "thumbnail_url": ""}


def transcribe_with_whisper(external_id: str) -> list:
    """Download audio from YouTube and transcribe with OpenAI Whisper.

    Returns list of dicts: [{text, start, duration}, ...]
    Requires yt-dlp and OPENAI_API_KEY in the environment.
    """
    import yt_dlp
    from openai import OpenAI

    client = OpenAI()
    url = f"https://www.youtube.com/watch?v={external_id}"

    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio",
            "outtmpl": os.path.join(tmpdir, "audio.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        files = os.listdir(tmpdir)
        if not files:
            raise RuntimeError("yt-dlp produced no output file")
        audio_path = os.path.join(tmpdir, files[0])

        with open(audio_path, "rb") as f:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="ja",
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

    return [
        {
            "text": seg.text.strip(),
            "start": round(seg.start, 3),
            "duration": round(seg.end - seg.start, 3),
        }
        for seg in response.segments
        if seg.text.strip()
    ]


def fetch_youtube_transcript(video_id: str) -> list:
    """Fetch Japanese transcript from YouTube.

    Returns list of dicts: [{text, start, duration}, ...]
    Uses youtube-transcript-api v1.x API.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    try:
        transcript = api.fetch(video_id, languages=["ja"])
        return transcript.to_raw_data()
    except Exception as e:
        print(f"Transcript fetch failed for {video_id}: {e}")
        raise ValueError(f"No Japanese transcript available for video {video_id}")


# ---------------------------------------------------------------------------
# Cloze generation from transcript
# ---------------------------------------------------------------------------

_tokenizer = Tokenizer()


def _load_jlpt_vocab(conn: sqlite3.Connection) -> dict:
    """Load JLPT vocab map (expression → {level, meaning}) if the vocabulary table exists."""
    try:
        rows = conn.execute("SELECT expression, jlpt_level, meaning FROM vocabulary WHERE jlpt_level IS NOT NULL").fetchall()
        return {row[0]: {"level": row[1], "meaning": row[2]} for row in rows}
    except sqlite3.OperationalError:
        return {}


def _merge_transcript_to_sentences(transcript: list) -> list:
    """Merge subtitle segments into proper Japanese sentences.

    Returns list of dicts: [{text, start}, ...]
    """
    full_text = ""
    # Build a mapping of character offset to timestamp
    char_timestamps = []

    for seg in transcript:
        start_offset = len(full_text)
        full_text += seg["text"]
        char_timestamps.append((start_offset, seg["start"]))
        # Add space between segments only if they don't end with punctuation
        if not full_text.endswith(("。", "？", "！", "\n")):
            full_text += " "

    # Split into sentences at Japanese sentence-ending punctuation (full-width and half-width)
    raw_sentences = re.split(r'(?<=[。？！?!])\s*', full_text)

    sentences = []
    search_offset = 0
    for s in raw_sentences:
        s = s.strip()
        if not s or len(s) < 5:
            continue
        # Find the approximate timestamp for this sentence
        pos = full_text.find(s, search_offset)
        if pos >= 0:
            search_offset = pos + len(s)
        timestamp = 0.0
        for char_off, ts in char_timestamps:
            if char_off <= (pos if pos >= 0 else 0):
                timestamp = ts
            else:
                break
        sentences.append({"text": s, "start": timestamp})

    return sentences


def generate_video_exercises(video_id: str, transcript_json: str, conn: sqlite3.Connection, max_exercises: int = 12):
    """Generate cloze exercises from a video transcript and insert them."""
    transcript = json.loads(transcript_json)
    sentences = _merge_transcript_to_sentences(transcript)

    if not sentences:
        print("No sentences extracted from transcript.")
        return 0

    jlpt_vocab = _load_jlpt_vocab(conn)

    # Shuffle to get varied sentences
    random.shuffle(sentences)

    exercises_created = 0
    for sent_info in sentences:
        if exercises_created >= max_exercises:
            break

        sentence = sent_info["text"]
        timestamp = sent_info["start"]

        tokens = list(_tokenizer.tokenize(sentence))

        # Find candidates (same logic as exercise_generator.py)
        candidates = []
        for i, token in enumerate(tokens):
            pos = token.part_of_speech.split(",")[0]
            vocab_entry = jlpt_vocab.get(token.surface) or jlpt_vocab.get(token.base_form)

            if vocab_entry is not None:
                candidates.append((i, token, vocab_entry["level"], vocab_entry.get("meaning", "")))
            elif pos in ["助詞", "動詞"] and len(token.surface) > 0:
                candidates.append((i, token, None, ""))

        if not candidates:
            continue

        idx, chosen, jlpt_level, word_meaning = random.choice(candidates)
        correct_answer = chosen.surface
        pos = chosen.part_of_speech.split(",")[0]

        # Build question sentence
        parts = []
        for j, token in enumerate(tokens):
            parts.append("[＿＿＿]" if j == idx else token.surface)
        question_sentence = "".join(parts)

        # Use vocabulary meaning as hint if available; fall back to sentence translation
        if word_meaning:
            hint_chinese = word_meaning
        else:
            try:
                hint_chinese = translate_text(sentence, target="zh-TW")
            except Exception:
                hint_chinese = ""

        exercise_id = str(uuid.uuid4())
        conn.execute('''
            INSERT INTO video_exercises
            (exercise_id, video_id, full_sentence, question_sentence, correct_answer,
             part_of_speech, jlpt_level, hint_chinese, context_timestamp, created_timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            exercise_id, video_id, sentence, question_sentence, correct_answer,
            pos, jlpt_level, hint_chinese, timestamp, datetime.now().isoformat()
        ))

        exercises_created += 1
        try:
            print(f"  -> Video exercise {exercises_created}: blanked '{correct_answer}' (POS: {pos}, JLPT: N{jlpt_level or 'A'})")
        except UnicodeEncodeError:
            print(f"  -> Video exercise {exercises_created}: created (POS: {pos}, JLPT: N{jlpt_level or 'A'})")

    conn.commit()
    print(f"Created {exercises_created} video exercises for video {video_id}")
    return exercises_created


# ---------------------------------------------------------------------------
# Main import pipeline
# ---------------------------------------------------------------------------

def import_video(url: str, db_path: str, use_whisper: bool = False) -> dict:
    """Import a YouTube video: fetch metadata + transcript, generate exercises.

    Returns dict with video_id and title, or raises on error.
    If use_whisper=True, downloads audio and transcribes via OpenAI Whisper instead
    of using YouTube captions; falls back to captions if Whisper fails.
    """
    video_ext_id = parse_youtube_url(url)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    create_video_tables(conn)

    # Check if already imported
    existing = conn.execute("SELECT video_id, title, status FROM videos WHERE external_id = ?", (video_ext_id,)).fetchone()
    if existing:
        conn.close()
        return {"video_id": existing["video_id"], "title": existing["title"], "already_exists": True}

    # Fetch metadata
    meta = fetch_youtube_metadata(video_ext_id)

    # Fetch transcript
    if use_whisper:
        try:
            print("  Transcribing with Whisper (this may take a minute)...")
            transcript = transcribe_with_whisper(video_ext_id)
            print(f"  Whisper: {len(transcript)} segments")
        except Exception as e:
            print(f"  Whisper failed ({e}), falling back to YouTube captions")
            transcript = fetch_youtube_transcript(video_ext_id)
    else:
        transcript = fetch_youtube_transcript(video_ext_id)

    video_id = str(uuid.uuid4())
    transcript_json = json.dumps(transcript, ensure_ascii=False)

    # Estimate duration from last subtitle
    duration = 0
    if transcript:
        last = transcript[-1]
        duration = int(last.get("start", 0) + last.get("duration", 0))

    canonical_url = f"https://www.youtube.com/watch?v={video_ext_id}"

    conn.execute('''
        INSERT INTO videos
        (video_id, source, external_id, url, title, channel_name, thumbnail_url,
         transcript_json, duration_seconds, status, created_timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        video_id, "youtube", video_ext_id, canonical_url,
        meta["title"], meta["channel_name"], meta["thumbnail_url"],
        transcript_json, duration, "unprocessed", datetime.now().isoformat()
    ))
    conn.commit()

    # Generate cloze exercises — mark processed regardless so the video is visible
    try:
        generate_video_exercises(video_id, transcript_json, conn)
    except Exception as e:
        print(f"Exercise generation failed (video still saved): {e}")

    conn.execute("UPDATE videos SET status = 'processed' WHERE video_id = ?", (video_id,))
    conn.commit()

    conn.close()
    return {"video_id": video_id, "title": meta["title"], "already_exists": False}
