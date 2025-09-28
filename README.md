# KANJIDIC2 to SQLite Converter

A fast, memory-efficient tool for converting KANJIDIC2 XML data into a normalized SQLite database. Built with streaming XML parsing and batch processing for optimal performance.

![Build Database](https://github.com/trygu/kanjidic2-sqlite-builder/workflows/Build%20KANJIDIC2%20SQLite%20Database/badge.svg)

## Features

- **Memory Efficient**: Uses streaming XML parsing (`iterparse`) to handle large KANJIDIC2 files without loading everything into memory
- **Fast Processing**: Batch commits and optimized database schema for maximum performance
- **Normalized Schema**: Clean, normalized database structure for flexible querying
- **Data Quality**: Automatic deduplication and unique indexes prevent duplicate data
- **Smart Views**: Pre-built views for common use cases and app development
- **Export Support**: Built-in CSV/JSON export functionality for easy data access

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
1. Go to the [Releases page](https://github.com/username/kanjidic2-sqlite-builder/releases)
2. Download `kanjidic2.sqlite` from the latest release

### From CI Artifacts (Latest Build)
1. Go to [Actions](https://github.com/username/kanjidic2-sqlite-builder/actions)
2. Click on the latest successful build
3. Download the `kanjidic2-sqlite-*` artifact

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
        INTEGER jlpt "JLPT level"
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
        TEXT literal PK "View: export-ready format"
        TEXT readings_on "Semicolon-separated on readings"
        TEXT readings_kun "Semicolon-separated kun readings"
        TEXT meanings_en "Semicolon-separated meanings"
        INTEGER freq "Frequency rank"
        INTEGER grade "School grade"
        INTEGER jlpt "JLPT level"
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
  - `jlpt` - Japanese Language Proficiency Test level

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

### Smart Views

- **`kanji_priority`** - **Intelligent learning order for educational apps**
  - **What it gives you**: Kanji ranked by optimal learning sequence
  - **Priority algorithm**: Frequency (most common first) → Grade level → JLPT level
  - **Perfect for**: Curriculum planning, spaced repetition systems, beginner apps
  - **Use case**: "Show me the next 20 most important kanji to learn"
  - **Key field**: `priority_score` (lower = more important to learn first)

- **`kanji_seed`** - **Ready-to-use data format for rapid app development**
  - **What it gives you**: Complete kanji info in one row, no JOINs needed
  - **Data format**: Readings and meanings pre-concatenated with semicolons
  - **Perfect for**: Quick prototypes, mobile apps, CSV imports, simple lookups
  - **Use case**: "Give me all kanji data in the simplest possible format"
  - **Benefit**: Parse once, use everywhere - no complex SQL required

- **`kanji_stroke_neighbors`** - **Intelligent distractor generation for quizzes**
  - **What it gives you**: Kanji that look similar by stroke count (±2 strokes)
  - **Perfect for**: Multiple choice questions, "which kanji has X strokes?" games
  - **Use case**: User learns 水 (4 strokes) → show 木 (4), 火 (4), 天 (6) as alternatives

- **`kanji_radical_neighbors`** - **Radical-based learning connections**
  - **What it gives you**: Kanji sharing the same radicals for pattern recognition
  - **Perfect for**: Teaching radical concepts, "kanji family" learning
  - **Use case**: User learns 水 → show 海, 池, 泳 (all have water radical) for context

## Command Line Usage

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
# 🎯 For learning apps: Get top 100 learning-priority kanji
k2sqlite export --db output/kanjidic2.sqlite --view kanji_priority --format csv --limit 100 --output curriculum.csv

# 📱 For mobile apps: Get simple, ready-to-use kanji data
k2sqlite export --db output/kanjidic2.sqlite --view kanji_seed --format json --limit 1000 --output app_data.json

# 👶 For beginner apps: Get only Grade 1-2 kanji in learning order
k2sqlite export --db output/kanjidic2.sqlite --view kanji_priority --format csv --limit 200 --output beginner_kanji.csv

# 🔗 For APIs: Stream data to other systems
k2sqlite export --db output/kanjidic2.sqlite --view kanji_seed --format json | curl -X POST -d @- https://your-api.com/import
```

**Real-world examples:**
- **Flashcard app**: Use `kanji_priority` to show most important kanji first
- **Quiz game**: Use `kanji_seed` for simple lookups, neighbor views for wrong answers
- **Learning dashboard**: Export CSV to Excel for curriculum planning
- **Mobile app**: Load JSON into app database on first launch

Export Options:
- `--db`, `-d` - SQLite database path (required)
- `--view`, `-v` - View to export: `kanji_seed` or `kanji_priority` (default: kanji_seed)
- `--format`, `-f` - Output format: `csv` or `json` (default: csv)
- `--output`, `-o` - Output file path (default: stdout)
- `--limit`, `-l` - Limit number of records exported

## Automated Builds

This project uses GitHub Actions to automatically build and test the SQLite database:

- **On every push/PR**: Database is built and tested for quality
- **On releases**: Database artifact is attached to the GitHub release
- **Manual triggers**: You can manually trigger builds from the Actions tab

### CI/CD Features:
- ✅ **Automated Testing**: Runs full test suite
- ✅ **Database Validation**: Verifies row counts and data integrity
- ✅ **Artifact Storage**: SQLite database stored as downloadable artifact
- ✅ **Release Assets**: Automatic attachment to GitHub releases

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

Once you have your SQLite database, here are some useful queries:

### Basic Queries
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
```

### Using Smart Views
```sql
-- Get top 10 priority kanji for learning
SELECT literal, readings_on, readings_kun, meanings_en, priority_score
FROM kanji_priority
LIMIT 10;

-- Export-ready data
SELECT * FROM kanji_seed WHERE grade = 1 LIMIT 20;

-- Find similar kanji for quiz distractors
SELECT neighbor, neighbor_strokes, stroke_diff
FROM kanji_stroke_neighbors
WHERE kanji = '水'
ORDER BY stroke_diff, neighbor_strokes;

-- Find kanji sharing radicals
SELECT neighbor, shared_radical
FROM kanji_radical_neighbors
WHERE kanji = '水';
```

## Requirements

- Python 3.10+
- pandas >= 2.2

## Why This Architecture?

- **Streaming Processing**: Handles large XML files without memory issues
- **Batch Commits**: Optimizes database write performance
- **Normalized Design**: Enables flexible querying and joins for any application
- **Data Quality Assurance**: Automatic deduplication and unique constraints
- **Smart Views**: Pre-built queries for common app development patterns
- **Export Ready**: Built-in tools for generating app-ready data formats
- **Proper Indexing**: Ensures good query performance for all use cases

## Next Steps

- Add JMDict support for vocabulary data
- Implement additional export formats and filtering options
- Add more neighbor-finding algorithms for quiz generation
- Support for additional KANJIDIC2 fields (variants, codepoints)
- API endpoint wrapper for web applications
