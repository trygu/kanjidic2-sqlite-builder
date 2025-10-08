# KANJIDIC2 to SQLite Converter

A fast, memory-efficient tool for converting KANJIDIC2 XML data into a normalized SQLite database. Built with streaming XML parsing and batch processing for optimal performance.

![Build Database](https://github.com/trygu/kanjidic2-sqlite-builder/workflows/Build%20KANJIDIC2%20SQLite%20Database/badge.svg)

## Features

- **Memory Efficient**: Uses streaming XML parsing (`iterparse`) to handle large KANJIDIC2 files without loading everything into memory
- **Fast Processing**: Batch commits and optimized database schema for maximum performance
- **Normalized Schema**: Clean, normalized database structure for flexible querying
- **Data Quality**: Automatic deduplication and unique indexes prevent duplicate data
- **Foundation-First**: Provides solid database foundation for any kanji application
- **Export Support**: Basic CSV/JSON export for development and prototyping
- **Production Artifacts**: Generate complete packages with seed files, lookup maps, and manifest
- **Automated CI/CD**: GitHub Actions pipeline with comprehensive artifact generation and testing
- **Utility Scripts**: Schema documentation, specialized lookups, MCQ generation, and manifest tools

## Quick Start

```bash
# 1. Create virtual environment and install
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .

# 2. Convert KANJIDIC2.xml to SQLite (using included data file)
k2sqlite build --input data/kanjidic2.xml --db output/kanjidic2.sqlite
```

## Download Pre-built Database

Instead of building the database yourself, you can download a pre-built SQLite database from our GitHub releases or CI artifacts:

### From GitHub Releases
1. Go to the [Releases page](https://github.com/trygu/kanjidic2-sqlite-builder/releases)
2. Download `kanjidic2.sqlite` from the latest release
3. **NEW**: Also available - `kanjidic2-artifacts.tar.gz` containing the complete production package

### From CI Artifacts (Latest Build)
1. Go to [Actions](https://github.com/trygu/kanjidic2-sqlite-builder/actions)
2. Click on the latest successful build
3. Download artifacts:
   - `kanjidic2-sqlite-*` - Just the SQLite database
   - `kanjidic2-artifacts-*` - Complete production package with seed files, lookup maps, and manifest

The database is automatically rebuilt whenever changes are made to the codebase.

## Database Schema

The generated SQLite database contains the following tables:

```mermaid
erDiagram
    kanji {
        TEXT literal PK "The kanji character"
        INTEGER grade "School grade (1-6, 8)"
        INTEGER stroke_count "Number of strokes"
        INTEGER freq "Frequency rank (1=most common)"
        INTEGER jlpt "Modern JLPT level (1=N1, 2=N2, 3=N3, 4=N4, 5=N5)"
    }

    kanji_radical {
        TEXT literal FK "The kanji character"
        TEXT rad_value "Classical radical number"
    }

    kanji_reading {
        TEXT literal FK "The kanji character"
        TEXT type "Reading type: on/kun"
        TEXT reading "The actual reading"
    }

    kanji_meaning {
        TEXT literal FK "The kanji character"
        TEXT lang "Language code (en)"
        TEXT meaning "English meaning"
    }

    kanji_variant {
        TEXT literal FK "The kanji character"
        TEXT var_type "Variant type"
        TEXT value "Variant value"
    }

    kanji_priority {
        TEXT literal PK "View: priority sorted kanji"
        INTEGER priority_score "Calculated learning priority"
        TEXT readings_on "Semicolon-separated on readings"
        TEXT readings_kun "Semicolon-separated kun readings"
        TEXT meanings_en "Semicolon-separated meanings"
    }

    kanji_seed {
        TEXT literal PK "View: quiz-ready format"
        INTEGER lvl "JLPT level (5=N5, 4=N4, 3=N3, 2=N2, 1=N1)"
        INTEGER freq "Frequency rank"
        INTEGER grade "School grade"
        TEXT main_meaning "Primary English meaning"
        TEXT on_prime "On readings (・-separated)"
        TEXT kun_prime "Kun readings (・-separated)"
    }

    distractor_pool {
        INTEGER lvl "View: JLPT level for distractors"
        TEXT meaning "English meaning for quiz distractors"
    }

    kanji ||--o{ kanji_radical : contains
    kanji ||--o{ kanji_reading : has
    kanji ||--o{ kanji_meaning : means
    kanji ||--o{ kanji_variant : variants
```

### Core Tables
- **`kanji`** - Main kanji information
  - `literal` (PRIMARY KEY) - The kanji character
  - `grade` - School grade level (1-6 for elementary, 8 for secondary)
  - `stroke_count` - Number of strokes
  - `freq` - Frequency ranking (1 = most common)
  - `jlpt` - Modern JLPT level (1=N1, 2=N2, 3=N3, 4=N4, 5=N5)

- **`kanji_radical`** - Radical information
  - `literal` - The kanji character
  - `rad_value` - Classical radical number

- **`kanji_reading`** - Pronunciation readings
  - `literal` - The kanji character
  - `type` - Reading type (`'on'` or `'kun'`)
  - `reading` - The actual reading

- **`kanji_meaning`** - English meanings
  - `literal` - The kanji character
  - `lang` - Language code (defaults to `'en'`)
  - `meaning` - English meaning

- **`kanji_variant`** - Character variants
  - `literal` - The kanji character
  - `var_type` - Variant type
  - `value` - Variant value

### Indexes
- `idx_kanji_freq` - Frequency-based lookups
- `idx_reading` - Reading-based searches
- `idx_meaning` - Meaning-based searches
- **Unique indexes** prevent duplicates:
  - `ux_reading` - (literal, type, reading)
  - `ux_meaning` - (literal, meaning)
  - `ux_radical` - (literal, rad_value)
  - `ux_variant` - (literal, var_type, value)

### Essential Views

- **`kanji_priority`** - **Intelligent learning order**
  - **Purpose**: Kanji ranked by optimal learning sequence (frequency → grade → JLPT)
  - **Key field**: `priority_score` (lower = higher priority)
  - **Best for**: Apps that need "what should I learn next?" logic

- **`kanji_seed`** - **Quiz application contract**
  - **Purpose**: One row per kanji with normalized JLPT levels and clean data for quiz generation
  - **Key fields**: `lvl` (5=N5, 4=N4, 3=N3, 2=N2, 1=N1), `main_meaning`, `on_prime`, `kun_prime`
  - **Best for**: Quiz apps that need fast random kanji selection by JLPT level

- **`distractor_pool`** - **Quiz distractor generation**
  - **Purpose**: Pool of meanings by JLPT level for generating wrong answer choices
  - **Key fields**: `lvl`, `meaning`
  - **Best for**: Quiz apps that need to generate plausible wrong answers

### Modern JLPT Mapping

The database includes an intelligent JLPT level mapping system that converts historical KANJIDIC2 JLPT data (1-4) into modern JLPT levels (N1-N5). The mapping is materialized in the `lvl` column in `kanji_seed` and `distractor_pool` views. This ensures compatibility with modern learning applications.

- **N5 (Level 5)**: Grade 1-2 kanji + high-frequency characters (easiest)
- **N4 (Level 4)**: Grade 3-4 kanji + historical JLPT level 4
- **N3 (Level 3)**: Grade 5-6 kanji + historical JLPT level 3
- **N2 (Level 2)**: Historical JLPT level 2 + common secondary kanji
- **N1 (Level 1)**: Historical JLPT level 1 + advanced kanji (hardest)

**App Contract**: The `lvl` column in views uses reversed numbering (5=N5, 4=N4, 3=N3, 2=N2, 1=N1) to match common app expectations where higher numbers = easier levels.

This ensures your applications get practical N5 data (338 kanji) for modern Japanese learning, even though the original KANJIDIC2 only had levels 1-4.## Command Line Usage

### Build Database
```bash
# Using included KANJIDIC2 data
k2sqlite build --input data/kanjidic2.xml --db output/kanjidic2.sqlite --batch 500

# Using your own KANJIDIC2 file
k2sqlite build --input /path/to/your/KANJIDIC2.xml --db output/kanjidic2.sqlite --batch 500
```

Build Options:
- `--input`, `-i` - Path to KANJIDIC2.xml file (required)
  - Use `data/kanjidic2.xml` for the included dataset
  - Or provide your own KANJIDIC2.xml file path
- `--db`, `-o` - Output SQLite database path (required)
- `--batch`, `-b` - Number of kanji to process before committing to database (default: 500)
  - Higher values (1000+): Faster processing, more memory usage
  - Lower values (100-250): Slower processing, less memory usage, more frequent saves

### Export Data
```bash
# Basic CSV export
k2sqlite export --db output/kanjidic2.sqlite --view kanji_seed --format csv --limit 100 --output kanji.csv

# Basic JSON export
k2sqlite export --db output/kanjidic2.sqlite --view kanji_priority --format json --limit 50 --output priority.json

# Stream to stdout for further processing
k2sqlite export --db output/kanjidic2.sqlite --view kanji_seed --format csv | head -20
```

**Philosophy**: The export function provides basic data access. Your applications should implement their own specialized logic for:
- Quiz question generation
- Learning algorithms
- UI-specific data formatting
- Caching and performance optimization

Export Options:
- `--db`, `-d` - SQLite database path (required)
- `--view`, `-v` - View to export: `kanji_seed` or `kanji_priority` (default: kanji_seed)
- `--format`, `-f` - Output format: `csv` or `json` (default: csv)
- `--output`, `-o` - Output file path (default: stdout)
- `--limit`, `-l` - Limit number of records exported

### Generate Production Artifacts

The artifacts command generates a quiz-focused package optimized for kanji learning applications:

```bash
# Generate artifacts in output directory (recommended workflow)
make artifacts

# Or generate artifacts manually to different location
k2sqlite artifacts --db output/kanjidic2.sqlite --output-dir dist/

# Generate artifacts with custom version
k2sqlite artifacts --db output/kanjidic2.sqlite --output-dir output --version "v1.0.0"
```

**Generated Files**:
- `kanjidic2.sqlite` - Complete database with quiz-oriented views (`kanji_seed`, `distractor_pool`) and indexes
- `manifest.json` - Database metadata with JLPT level counts and quality metrics

Artifacts Options:
- `--db`, `-d` - SQLite database path (required)
- `--output-dir`, `-o` - Output directory (default: output)
- `--version`, `-v` - Version string for manifest (default: local-build)

### App Contract SQL Queries

The database includes optimized views for quiz applications:

```sql
-- Pick a random kanji for quiz
SELECT * FROM kanji_seed WHERE lvl=? ORDER BY RANDOM() LIMIT 1;

-- Get distractors for multiple choice
SELECT meaning FROM distractor_pool WHERE lvl=? AND meaning<>? ORDER BY RANDOM() LIMIT 3;
```

**View Schema**:
- `kanji_seed`: literal, lvl (5=N5, 4=N4, 3=N3, 2=N2, 1=N1), freq, grade, main_meaning, on_prime, kun_prime
- `distractor_pool`: lvl, meaning

**Example Usage**:
```python
import sqlite3
con = sqlite3.connect('output/kanjidic2.sqlite')

# Get N5 kanji for quiz
cur = con.execute("SELECT * FROM kanji_seed WHERE lvl=5 ORDER BY RANDOM() LIMIT 1")
kanji = cur.fetchone()  # ('雨', 5, 950, 1, 'rain', 'ウ', 'さめ・あま-・あめ')

# Get distractors for this kanji
cur = con.execute("SELECT meaning FROM distractor_pool WHERE lvl=5 AND meaning<>? ORDER BY RANDOM() LIMIT 3", (kanji[4],))
distractors = [row[0] for row in cur.fetchall()]  # ['science', 'many', 'part']
```

## Automated Builds

This project uses GitHub Actions to automatically build and test the SQLite database with quiz-focused artifacts:

- **On every push/PR**: Database is built, tested, and production artifacts generated
- **On releases**: Database and complete artifact package attached to GitHub releases
- **Manual triggers**: You can manually trigger builds from the Actions tab

### CI/CD Features:
- ✅ **Automated Testing**: Runs full test suite
- ✅ **Database Validation**: Verifies row counts and data integrity
- ✅ **Artifact Generation**: Complete production package with seed files, lookup maps, and manifest
- ✅ **Dual Artifacts**: Both individual database file and comprehensive artifact package
- ✅ **Release Assets**: Automatic attachment to GitHub releases
- ✅ **Version Tracking**: Artifacts include version information and SHA256 checksums

### Generated CI Artifacts:
- `kanjidic2.sqlite` - The core database file
- `kanjidic2-artifacts/` - Complete production package containing:
  - `kanjidic2.sqlite` - Database copy
  - `kanji_seed.csv` - Top 500 kanji (CSV format)
  - `kanji_seed.json` - Top 500 kanji (JSON format)
  - `map_char_to_meaning.json` - Character → meanings lookup
  - `map_char_to_readings.json` - Character → readings lookup
  - `manifest.json` - File inventory with SHA256 checksums

## Development

### Running Tests
```bash
# Install development dependencies
pip install -e .[dev]

# Run tests
pytest

# Run tests with coverage
pytest --cov=k2sqlite
```

The test suite uses a sample KANJIDIC2.xml file in `tests/fixtures/` to verify the conversion process works correctly.

### Code Quality
```bash
# Format code
black src/ tests/

# Lint code
ruff src/ tests/
```

## Example Queries

Here are practical SQL queries for common kanji application scenarios:

### Basic Lookups
```sql
-- Find all grade 1 kanji with their meanings
SELECT k.literal, k.stroke_count, GROUP_CONCAT(m.meaning, '; ') as meanings
FROM kanji k
JOIN kanji_meaning m ON k.literal = m.literal
WHERE k.grade = 1
GROUP BY k.literal
ORDER BY k.freq;

-- Find kanji by reading
SELECT DISTINCT k.literal, k.freq
FROM kanji k
JOIN kanji_reading r ON k.literal = r.literal
WHERE r.reading = 'スイ' AND r.type = 'on'
ORDER BY k.freq;

-- Search kanji by meaning
SELECT k.literal, k.freq, k.grade, m.meaning
FROM kanji k
JOIN kanji_meaning m ON k.literal = m.literal
WHERE m.meaning LIKE '%water%'
ORDER BY k.freq;
```

### Learning Curriculum Queries
```sql
-- Get learning progression: most common kanji first
SELECT literal, readings_on, readings_kun, meanings_en, freq
FROM kanji_seed
WHERE freq IS NOT NULL
ORDER BY freq
LIMIT 100;

-- Grade-based curriculum (elementary school progression)
SELECT grade, COUNT(*) as kanji_count,
       MIN(freq) as easiest_freq, MAX(freq) as hardest_freq
FROM kanji
WHERE grade BETWEEN 1 AND 6
GROUP BY grade
ORDER BY grade;

-- JLPT study sets (using new lvl column format)
SELECT literal, main_meaning, on_prime, kun_prime, freq
FROM kanji_seed
WHERE lvl = 5  -- N5 level kanji (easiest)
  AND freq IS NOT NULL  -- Only kanji with frequency data
ORDER BY freq
LIMIT 20;

-- All JLPT levels with counts (using new lvl format)
SELECT lvl,
       CASE lvl
         WHEN 5 THEN 'N5 (easiest)'
         WHEN 4 THEN 'N4'
         WHEN 3 THEN 'N3'
         WHEN 2 THEN 'N2'
         WHEN 1 THEN 'N1 (hardest)'
       END as level_name,
       COUNT(*) as kanji_count,
       COUNT(CASE WHEN freq IS NOT NULL THEN 1 END) as with_frequency
FROM kanji_seed
GROUP BY lvl
ORDER BY lvl DESC;
```

### Quiz Generation Queries
```sql
-- Generate multiple choice distractors (same grade level)
SELECT k1.literal as target,
       k2.literal as distractor,
       k1.grade, k2.freq
FROM kanji k1, kanji k2
WHERE k1.literal = '水'
  AND k2.grade = k1.grade
  AND k2.literal != k1.literal
  AND k2.freq IS NOT NULL
ORDER BY k2.freq
LIMIT 3;

-- Find kanji with similar stroke counts for visual confusion
SELECT k1.literal as target,
       k2.literal as similar_looking,
       k1.stroke_count, k2.stroke_count,
       ABS(k1.stroke_count - k2.stroke_count) as stroke_diff
FROM kanji k1, kanji k2
WHERE k1.literal = '人'
  AND ABS(k1.stroke_count - k2.stroke_count) <= 1
  AND k1.literal != k2.literal
  AND k2.freq <= 1000  -- Only common kanji
ORDER BY stroke_diff, k2.freq;

-- Reading confusion pairs (same reading, different kanji)
SELECT r1.literal as kanji1, r2.literal as kanji2, r1.reading
FROM kanji_reading r1, kanji_reading r2
WHERE r1.reading = r2.reading
  AND r1.type = r2.type
  AND r1.literal != r2.literal
  AND r1.reading = 'コウ'  -- Example: 高, 校, 考, etc.
ORDER BY r1.literal;
```

### Progress Tracking Queries
```sql
-- Kanji distribution by difficulty
SELECT
  CASE
    WHEN freq <= 100 THEN 'Very Common (1-100)'
    WHEN freq <= 500 THEN 'Common (101-500)'
    WHEN freq <= 1000 THEN 'Intermediate (501-1000)'
    ELSE 'Advanced (1000+)'
  END as difficulty,
  COUNT(*) as kanji_count
FROM kanji
WHERE freq IS NOT NULL
GROUP BY
  CASE
    WHEN freq <= 100 THEN 'Very Common (1-100)'
    WHEN freq <= 500 THEN 'Common (101-500)'
    WHEN freq <= 1000 THEN 'Intermediate (501-1000)'
    ELSE 'Advanced (1000+)'
  END;

-- Find kanji missing readings (data quality check)
SELECT k.literal, k.grade, k.freq
FROM kanji k
LEFT JOIN kanji_reading r ON k.literal = r.literal
WHERE r.literal IS NULL
  AND k.freq IS NOT NULL
ORDER BY k.freq;
```

### Advanced Analysis
```sql
-- Most common radicals across all kanji
SELECT rad_value, COUNT(*) as kanji_count
FROM kanji_radical r
JOIN kanji k ON r.literal = k.literal
WHERE k.freq IS NOT NULL
GROUP BY rad_value
ORDER BY kanji_count DESC
LIMIT 10;

-- Kanji with most readings (complex characters)
SELECT k.literal, k.freq, k.grade,
       COUNT(r.reading) as reading_count
FROM kanji k
JOIN kanji_reading r ON k.literal = r.literal
GROUP BY k.literal
ORDER BY reading_count DESC
LIMIT 20;

-- Find "gateway" kanji (common + low grade = good for beginners)
SELECT literal, meanings_en, readings_on, freq, grade,
       (1000 - freq) + (10 - grade) as beginner_score
FROM kanji_seed
WHERE freq IS NOT NULL AND grade IS NOT NULL
ORDER BY beginner_score DESC
LIMIT 50;
```

### Using Views for App Development
```sql
-- Priority-based learning queue
SELECT literal, on_prime, kun_prime, main_meaning, priority_score
FROM kanji_priority
LIMIT 10;

-- Quiz app: Pick a random kanji for level N4
SELECT literal, main_meaning, on_prime, kun_prime
FROM kanji_seed WHERE lvl = 4 ORDER BY RANDOM() LIMIT 1;

-- Quiz app: Get distractor meanings for N4 level (excluding correct answer)
SELECT meaning FROM distractor_pool
WHERE lvl = 4 AND meaning != 'water'
ORDER BY RANDOM() LIMIT 3;

-- Quiz app: Level distribution for UI
SELECT lvl,
       CASE lvl
         WHEN 5 THEN 'N5 (easiest)'
         WHEN 4 THEN 'N4'
         WHEN 3 THEN 'N3'
         WHEN 2 THEN 'N2'
         WHEN 1 THEN 'N1 (hardest)'
       END as level_name,
       COUNT(*) as kanji_count
FROM kanji_seed
GROUP BY lvl
ORDER BY lvl DESC;
```

## Requirements

- Python 3.10+
- pandas >= 2.2

## Why This Architecture?

- **Database-First Design**: Focus on providing a solid, clean data foundation
- **Streaming Processing**: Handles large XML files without memory issues
- **Batch Commits**: Optimizes database write performance
- **Normalized Schema**: Enables any type of kanji application to be built on top
- **Data Quality**: Automatic deduplication and constraints ensure clean data
- **Simple Views**: Two essential views for common patterns, nothing more
- **App Freedom**: Your applications implement their own specialized logic
- **Proper Indexing**: Ensures good performance for all query patterns

## Next Steps

This database is designed to be the foundation for specialized kanji applications. Consider building:
- **Spaced repetition systems** using the priority scoring
- **Quiz generators** with grade/JLPT-based difficulty matching
- **Learning dashboards** with progress tracking
- **Mobile flashcard apps** using the seed view for simple data loading
- **API services** that add application-specific logic on top
