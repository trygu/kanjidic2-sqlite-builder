from pathlib import Path
import sqlite3
from k2sqlite.builder import build_sqlite

def test_build_sqlite(tmp_path: Path):
    xml = Path(__file__).with_suffix("").parents[0] / "fixtures" / "sample_kanjidic2.xml"
    db = tmp_path / "k2.sqlite"
    n = build_sqlite(xml, db, batch_size=10)
    assert n == 1
    con = sqlite3.connect(db)
    cur = con.execute("select literal, grade, stroke_count, freq, jlpt from kanji")
    row = cur.fetchone()
    assert row == ("水", 1, 4, 60, 5)  # Modern JLPT: Grade 1 kanji -> N5 (level 5)
    cur = con.execute("select type, reading from kanji_reading where literal='水' order by type")
    rows = cur.fetchall()
    assert rows == [("kun","みず"),("on","スイ")]
    con.close()
