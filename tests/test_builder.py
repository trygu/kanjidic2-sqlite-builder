from pathlib import Path
import sqlite3
from k2sqlite.builder import build_sqlite


def test_build_sqlite(tmp_path: Path):
    xml = (
        Path(__file__).with_suffix("").parents[0] / "fixtures" / "sample_kanjidic2.xml"
    )
    db = tmp_path / "k2.sqlite"
    n = build_sqlite(xml, db, batch_size=10)
    assert n == 1
    con = sqlite3.connect(db)
    
    # Test main kanji table
    cur = con.execute("select literal, grade, stroke_count, freq, jlpt from kanji")
    row = cur.fetchone()
    assert row == ("水", 1, 4, 60, 5)  # Modern JLPT: Grade 1 kanji -> N5 (level 5)
    
    # Test quiz app contract views exist
    cur = con.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")
    views = [row[0] for row in cur.fetchall()]
    assert "kanji_seed" in views
    assert "distractor_pool" in views
    
    # Test kanji_seed view format - water should be N5 so lvl=5
    cur = con.execute("SELECT literal, lvl, main_meaning, on_prime, kun_prime FROM kanji_seed WHERE literal='水'")
    seed_row = cur.fetchone()
    assert seed_row[0] == "水"  # literal
    assert seed_row[1] == 5     # lvl: N5 level 
    assert seed_row[2] == "water"  # main_meaning
    assert seed_row[3] == "スイ"    # on_prime
    assert seed_row[4] == "みず"    # kun_prime
    
    # Test distractor_pool view exists and has correct format
    cur = con.execute("SELECT lvl, meaning FROM distractor_pool WHERE meaning='water'")
    distractor_row = cur.fetchone()
    assert distractor_row[0] == 5      # lvl
    assert distractor_row[1] == "water"  # meaning
    
    # Test readings
    cur = con.execute(
        "select type, reading from kanji_reading where literal='水' order by type"
    )
    rows = cur.fetchall()
    assert rows == [("kun","みず"),("on","スイ")]
    con.close()
