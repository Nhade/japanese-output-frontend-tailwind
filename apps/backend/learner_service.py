import sqlite3
import json
from datetime import datetime

def create_learner_tables(conn):
    """Create learner_profiles table if it doesn't exist."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS learner_profiles (
            user_id TEXT PRIMARY KEY,
            profile_json TEXT,
            updated_at TEXT
        )
    ''')
    conn.commit()

def get_default_profile():
    return {
        "level_est": "N5",
        "weak_points": [],
        "strong_points": [],
        "feedback_preference": "gentle",
        "current_focus": {
            "tag": None,
            "progress": 0,
            "target": 5,
            "started_at": None
        },
        "stats": {
            "by_pos_attempt": {},
            "by_pos_wrong": {},
            "by_jlpt_attempt": {},
            "by_jlpt_wrong": {}
        }
    }

def refresh_focus(profile):
    """
    Ensure a valid current_focus exists.
    If missing or None, pick from weak_points or default.
    """
    focus = profile.get("current_focus") or {}
    
    # If tag is missing or we force rotation (logic to be added if needed)
    if not focus.get("tag"):
        weak_points = profile.get("weak_points", [])
        new_tag = weak_points[0] if weak_points else "Vocabulary" # Default fallback
        
        focus = {
            "tag": new_tag,
            "progress": 0,
            "target": 5,
            "started_at": datetime.now().isoformat()
        }
        profile["current_focus"] = focus
    
    return profile

def get_learner_profile(conn, user_id):
    """Fetch learner profile or create default if missing."""
    row = conn.execute('SELECT profile_json FROM learner_profiles WHERE user_id = ?', (user_id,)).fetchone()
    
    if row:
        profile = json.loads(row['profile_json'])
        # P2 Migration: Ensure current_focus exists
        if "current_focus" not in profile:
            profile["current_focus"] = get_default_profile()["current_focus"]
            # Save immediately to fix schema
            # But we can just return it and let next update save it, 
            # Or simpler: just let refresh_focus handle it during updates/reads if we call it.
            # For read-consistency, let's just patch it in memory.
        return resolve_focus_display(profile)
    else:
        # Create default
        profile = get_default_profile()
        # Initial focus
        refresh_focus(profile)
        
        conn.execute('''
            INSERT INTO learner_profiles (user_id, profile_json, updated_at)
            VALUES (?, ?, ?)
        ''', (user_id, json.dumps(profile), datetime.now().isoformat()))
        conn.commit()
        return profile

def resolve_focus_display(profile):
    """Ensure focus is set for display purposes even if DB has old data."""
    if not profile.get("current_focus", {}).get("tag"):
        refresh_focus(profile)
    return profile

def update_learner_profile(conn, user_id, exercise_info, is_correct):
    """
    Update learner stats and recompute weak/strong points.
    exercise_info: dict with 'part_of_speech', 'jlpt_level'
    """
    profile = get_learner_profile(conn, user_id)
    stats = profile.get("stats", {})
    
    pos = exercise_info.get('part_of_speech', 'unknown')
    jlpt = exercise_info.get('jlpt_level', 'unknown')
    
    # Initialize dicts if missing (migration safety)
    for key in ["by_pos_attempt", "by_pos_wrong", "by_jlpt_attempt", "by_jlpt_wrong"]:
        if key not in stats:
            stats[key] = {}

    # Update counts
    stats["by_pos_attempt"][pos] = stats["by_pos_attempt"].get(pos, 0) + 1
    stats["by_jlpt_attempt"][jlpt] = stats["by_jlpt_attempt"].get(jlpt, 0) + 1
    
    if not is_correct:
        stats["by_pos_wrong"][pos] = stats["by_pos_wrong"].get(pos, 0) + 1
        stats["by_jlpt_wrong"][jlpt] = stats["by_jlpt_wrong"].get(jlpt, 0) + 1

    # Recompute Weak Points (Focus on POS for now)
    # Filter for items with at least 3 attempts to avoid noise
    pos_error_rates = []
    for p, attempts in stats["by_pos_attempt"].items():
        if attempts >= 3:
            wrong = stats["by_pos_wrong"].get(p, 0)
            rate = wrong / attempts
            pos_error_rates.append((p, rate))
    
    # Sort by error rate desc
    pos_error_rates.sort(key=lambda x: x[1], reverse=True)
    
    # Top 3 weak
    profile["weak_points"] = [p[0] for p in pos_error_rates[:3]]
    
    # Strong points (Bottom 2 error rates, need minimal attempts too)
    strong_candidates = [p[0] for p in pos_error_rates if p[1] < 0.2] # < 20% error
    profile["strong_points"] = strong_candidates[:3]

    # P2: Learning Focus Logic
    # 1. Ensure we have a focus
    refresh_focus(profile)
    focus = profile["current_focus"]
    
    # 2. Check overlap (Case insensitive match or exact?)
    # POS in DB are usually capitalized e.g. "Particle", "Verb".
    # Focus tag comes from weak_points which comes from POS.
    # So direct match should work.
    if focus["tag"] == pos:
        # Increment progress
        # We can count ANY attempt, or only correct/wrong?
        # Plan says "user answers a question tagged with focus" -> Any attempt is fine to show effort.
        focus["progress"] += 1
        
        # 3. Check completion
        if focus["progress"] >= focus["target"]:
            # Rotate logic:
            # Pick next weak point that is DIFFERENT from current
            weak_points = profile.get("weak_points", [])
            next_tag = "General"
            
            # Simple rotation: find current index, take next, or just take top if current is gone
            # If current tag is still #1 weak point, maybe keep it? 
            # OR force rotation to prevent boredom.
            # Let's force rotation to the next available weak point implementation.
            
            candidates = [wp for wp in weak_points if wp != focus["tag"]]
            if candidates:
                next_tag = candidates[0]
            else:
                # If no other weak points, loop back or generic
                # If no weak points exist yet, default to general practice focus
                next_tag = "Vocabulary" if focus["tag"] != "Vocabulary" else "Grammar"
            
            old_tag = focus["tag"]
            print(f"FOCUS ROTATION: {old_tag} -> {next_tag}")

            profile["current_focus"] = {
                "tag": next_tag,
                "progress": 0,
                "target": 5,
                "started_at": datetime.now().isoformat()
            }
        else:
            # Safeguard: Clamp at target (shouldn't be needed with >= check, but good for data integrity)
            profile["current_focus"]["progress"] = min(focus["progress"], focus["target"])

    # Save
    profile["stats"] = stats
    profile["updated_at"] = datetime.now().isoformat()
    
    conn.execute('''
        UPDATE learner_profiles 
        SET profile_json = ?, updated_at = ?
        WHERE user_id = ?
    ''', (json.dumps(profile), datetime.now().isoformat(), user_id))
    conn.commit()
    
    return profile

def backfill_learner_profile(conn, user_id):
    """
    Rebuild learner profile stats from all existing answer logs.
    """
    # 1. Reset profile stats
    profile = get_learner_profile(conn, user_id)
    stats = {
        "by_pos_attempt": {},
        "by_pos_wrong": {},
        "by_jlpt_attempt": {},
        "by_jlpt_wrong": {}
    }
    
    # 2. Query all logs for this user
    # Join with exercise to get POS and JLPT
    rows = conn.execute('''
        SELECT al.is_correct, e.part_of_speech, e.jlpt_level
        FROM answer_log al
        JOIN exercise e ON al.exercise_id = e.exercise_id
        WHERE al.user_id = ?
    ''', (user_id,)).fetchall()
    
    # 3. Aggregate
    for row in rows:
        pos = row['part_of_speech'] if row['part_of_speech'] else 'unknown'
        jlpt = row['jlpt_level'] if row['jlpt_level'] else 'unknown'
        is_correct = bool(row['is_correct'])
        
        # Attempts
        stats["by_pos_attempt"][pos] = stats["by_pos_attempt"].get(pos, 0) + 1
        stats["by_jlpt_attempt"][jlpt] = stats["by_jlpt_attempt"].get(jlpt, 0) + 1
        
        # Wrongs
        if not is_correct:
            stats["by_pos_wrong"][pos] = stats["by_pos_wrong"].get(pos, 0) + 1
            stats["by_jlpt_wrong"][jlpt] = stats["by_jlpt_wrong"].get(jlpt, 0) + 1
            
    # 4. Recompute Weak Points (Reuse logic or copy it)
    # Copied logic for simplicity & independence
    pos_error_rates = []
    for p, attempts in stats["by_pos_attempt"].items():
        if attempts >= 3:
            wrong = stats["by_pos_wrong"].get(p, 0)
            rate = wrong / attempts
            pos_error_rates.append((p, rate))
            
    pos_error_rates.sort(key=lambda x: x[1], reverse=True)
    
    profile["weak_points"] = [p[0] for p in pos_error_rates[:3]]
    strong_candidates = [p[0] for p in pos_error_rates if p[1] < 0.2]
    profile["strong_points"] = strong_candidates[:3]
    
    profile["stats"] = stats
    profile["updated_at"] = datetime.now().isoformat()
    
    # Save
    conn.execute('''
        UPDATE learner_profiles 
        SET profile_json = ?, updated_at = ?
        WHERE user_id = ?
    ''', (json.dumps(profile), datetime.now().isoformat(), user_id))
    conn.commit()
    
    return profile
