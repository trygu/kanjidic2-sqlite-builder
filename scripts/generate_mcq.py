#!/usr/bin/env python3
"""
MCQ (Multiple Choice Question) Generator for Kanji Learning

This script generates quiz datasets from the KANJIDIC2 SQLite database.
It creates questions with one correct answer and plausible distractors.

Usage:
    python scripts/generate_mcq.py --db output/kanjidic2.sqlite --count 100 --output quizzes/

Generated Questions:
    - Meaning → Character (What kanji means "water"?)
    - Character → Meaning (What does 水 mean?)
    - Reading → Character (What kanji has reading "みず"?)
    - Character → Reading (How do you read 水?)
"""
import argparse
import json
import random
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple


def get_kanji_data(conn: sqlite3.Connection, limit: int = 1000) -> List[Dict]:
    """Fetch kanji data with meanings and readings."""
    query = """
    SELECT
        k.literal,
        GROUP_CONCAT(km.meaning, ';') as meanings,
        GROUP_CONCAT(CASE WHEN kr.type = 'on' THEN kr.reading END, ';') as on_readings,
        GROUP_CONCAT(CASE WHEN kr.type = 'kun' THEN kr.reading END, ';') as kun_readings,
        k.freq
    FROM kanji k
    LEFT JOIN kanji_meaning km ON k.literal = km.literal AND km.lang = 'en'
    LEFT JOIN kanji_reading kr ON k.literal = kr.literal
    WHERE k.freq IS NOT NULL
    GROUP BY k.literal
    ORDER BY k.freq
    LIMIT ?
    """

    kanji_data = []
    for row in conn.execute(query, (limit,)):
        literal, meanings, on_readings, kun_readings, freq = row

        meanings_list = [m.strip() for m in (meanings or "").split(";") if m.strip()]
        on_list = [r.strip() for r in (on_readings or "").split(";") if r.strip()]
        kun_list = [r.strip() for r in (kun_readings or "").split(";") if r.strip()]

        if meanings_list:  # Only include kanji with meanings
            kanji_data.append(
                {
                    "literal": literal,
                    "meanings": meanings_list,
                    "on_readings": on_list,
                    "kun_readings": kun_list,
                    "freq": freq,
                }
            )

    return kanji_data


def generate_meaning_to_char_questions(
    kanji_data: List[Dict], count: int
) -> List[Dict]:
    """Generate 'What kanji means X?' questions."""
    questions = []
    used_meanings = set()

    for _ in range(count):
        # Pick a random kanji
        target = random.choice(kanji_data)

        # Pick a meaning that hasn't been used
        available_meanings = [m for m in target["meanings"] if m not in used_meanings]
        if not available_meanings:
            continue

        meaning = random.choice(available_meanings)
        used_meanings.add(meaning)

        # Generate distractors (wrong answers)
        distractors = []
        for _ in range(3):
            distractor = random.choice(kanji_data)
            if distractor["literal"] != target["literal"]:
                distractors.append(distractor["literal"])

        choices = [target["literal"]] + distractors
        random.shuffle(choices)

        questions.append(
            {
                "type": "meaning_to_char",
                "question": f"What kanji means '{meaning}'?",
                "choices": choices,
                "correct": target["literal"],
                "explanation": f"The kanji {target['literal']} means '{meaning}'",
            }
        )

    return questions


def generate_char_to_meaning_questions(
    kanji_data: List[Dict], count: int
) -> List[Dict]:
    """Generate 'What does X mean?' questions."""
    questions = []
    used_chars = set()

    for _ in range(count):
        # Pick a random kanji that hasn't been used
        available_kanji = [k for k in kanji_data if k["literal"] not in used_chars]
        if not available_kanji:
            break

        target = random.choice(available_kanji)
        used_chars.add(target["literal"])

        if not target["meanings"]:
            continue

        correct_meaning = target["meanings"][0]  # Use first meaning

        # Generate distractor meanings
        distractors = []
        attempts = 0
        while len(distractors) < 3 and attempts < 20:
            distractor = random.choice(kanji_data)
            if distractor["meanings"] and distractor["literal"] != target["literal"]:
                meaning = distractor["meanings"][0]
                if meaning != correct_meaning and meaning not in distractors:
                    distractors.append(meaning)
            attempts += 1

        choices = [correct_meaning] + distractors
        random.shuffle(choices)

        questions.append(
            {
                "type": "char_to_meaning",
                "question": f"What does {target['literal']} mean?",
                "choices": choices,
                "correct": correct_meaning,
                "explanation": f"The kanji {target['literal']} means '{correct_meaning}'",
            }
        )

    return questions


def generate_reading_questions(
    kanji_data: List[Dict], count: int, reading_type: str = "kun"
) -> List[Dict]:
    """Generate reading-based questions."""
    questions = []
    used_chars = set()

    for _ in range(count):
        # Pick a random kanji with the specified reading type
        available_kanji = [
            k
            for k in kanji_data
            if k["literal"] not in used_chars and k[f"{reading_type}_readings"]
        ]
        if not available_kanji:
            break

        target = random.choice(available_kanji)
        used_chars.add(target["literal"])

        reading = target[f"{reading_type}_readings"][0]

        # Generate distractors
        distractors = []
        for _ in range(3):
            distractor = random.choice(kanji_data)
            if (
                distractor["literal"] != target["literal"]
                and distractor[f"{reading_type}_readings"]
            ):
                distractors.append(distractor[f"{reading_type}_readings"][0])

        choices = [reading] + distractors
        random.shuffle(choices)

        questions.append(
            {
                "type": f"char_to_{reading_type}_reading",
                "question": f"How do you read {target['literal']} ({reading_type})? ",
                "choices": choices,
                "correct": reading,
                "explanation": f"The {reading_type} reading of {target['literal']} is '{reading}'",
            }
        )

    return questions


def main():
    parser = argparse.ArgumentParser(
        description="Generate MCQ questions from KANJIDIC2 database"
    )
    parser.add_argument("--db", "-d", required=True, help="SQLite database path")
    parser.add_argument("--output", "-o", default="mcq_output", help="Output directory")
    parser.add_argument(
        "--count", "-c", type=int, default=100, help="Questions per type"
    )
    parser.add_argument(
        "--kanji-limit",
        "-l",
        type=int,
        default=1000,
        help="Limit kanji pool (by frequency)",
    )

    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)

    print(f"Loading kanji data (limit: {args.kanji_limit})...")
    kanji_data = get_kanji_data(conn, args.kanji_limit)
    print(f"Loaded {len(kanji_data)} kanji")

    # Generate different question types
    print(f"Generating {args.count} questions of each type...")

    all_questions = []

    # Meaning → Character questions
    meaning_to_char = generate_meaning_to_char_questions(kanji_data, args.count)
    all_questions.extend(meaning_to_char)

    # Character → Meaning questions
    char_to_meaning = generate_char_to_meaning_questions(kanji_data, args.count)
    all_questions.extend(char_to_meaning)

    # Reading questions
    kun_reading_qs = generate_reading_questions(kanji_data, args.count, "kun")
    all_questions.extend(kun_reading_qs)

    on_reading_qs = generate_reading_questions(kanji_data, args.count, "on")
    all_questions.extend(on_reading_qs)

    # Save all questions
    with open(output_dir / "all_questions.json", "w", encoding="utf-8") as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=2)

    # Save by type
    question_types = {
        "meaning_to_char": meaning_to_char,
        "char_to_meaning": char_to_meaning,
        "kun_readings": kun_reading_qs,
        "on_readings": on_reading_qs,
    }

    for q_type, questions in question_types.items():
        with open(output_dir / f"{q_type}.json", "w", encoding="utf-8") as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)

    conn.close()

    print(f"✅ Generated {len(all_questions)} total questions")
    print(f"📁 Output saved to: {output_dir}")
    print("📊 Question breakdown:")
    for q_type, questions in question_types.items():
        print(f"  - {q_type}: {len(questions)} questions")


if __name__ == "__main__":
    main()
