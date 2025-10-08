import sqlite3


def ci_sanity_checks(db_path):
    """Run CI sanity checks on the SQLite database."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Log level distribution
    print("Level distribution:")
    for row in cur.execute("SELECT lvl, COUNT(*) FROM kanji_seed GROUP BY lvl"):
        print(row)

    # Check for missing main_meaning
    missing_meaning_count = cur.execute(
        "SELECT COUNT(*) FROM kanji_seed WHERE main_meaning IS NULL"
    ).fetchone()[0]
    print(f"Missing main_meaning: {missing_meaning_count}")

    # Check for missing readings
    missing_readings_count = cur.execute(
        "SELECT COUNT(*) FROM kanji_seed WHERE on_prime IS NULL AND kun_prime IS NULL"
    ).fetchone()[0]
    print(f"Missing readings: {missing_readings_count}")

    # Log top 20 kanji with missing readings
    print("Top 20 kanji with missing readings:")
    for row in cur.execute(
        "SELECT literal, main_meaning FROM kanji_seed WHERE on_prime IS NULL AND kun_prime IS NULL LIMIT 20"
    ):
        print(row)

    conn.close()


if __name__ == "__main__":
    ci_sanity_checks("output/kanjidic2.sqlite")
