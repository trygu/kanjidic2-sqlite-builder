#!/usr/bin/env python3
"""
Standalone Manifest Generator

Creates detailed manifests for any directory containing kanji data files.
Useful for version control, integrity checking, and API documentation.

Usage:
    python scripts/generate_manifest.py --dir artifacts/ --version "v1.0.0"
    python scripts/generate_manifest.py --dir releases/v2/ --include-checksums
"""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, List


def calculate_sha256(filepath: Path) -> str:
    """Calculate SHA256 hash of a file."""
    hash_sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


def get_sqlite_stats(db_path: Path) -> Dict[str, Any]:
    """Get statistics from SQLite database."""
    try:
        conn = sqlite3.connect(db_path)

        # Get table counts
        table_stats = {}
        for table_name in ["kanji", "kanji_reading", "kanji_meaning", "kanji_variant"]:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                table_stats[table_name] = count
            except sqlite3.OperationalError:
                continue

        # Get view counts if they exist
        view_stats = {}
        for view_name in ["kanji_seed", "kanji_priority"]:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {view_name}").fetchone()[0]
                view_stats[view_name] = count
            except sqlite3.OperationalError:
                continue

        conn.close()

        return {
            "type": "sqlite_database",
            "tables": table_stats,
            "views": view_stats,
            "total_kanji": table_stats.get("kanji", 0),
        }
    except Exception as e:
        return {"type": "sqlite_database", "error": str(e)}


def get_json_stats(json_path: Path) -> Dict[str, Any]:
    """Get statistics from JSON file."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return {
                "type": "json_array",
                "items": len(data),
                "sample_keys": (
                    list(data[0].keys()) if data and isinstance(data[0], dict) else None
                ),
            }
        elif isinstance(data, dict):
            stats = {"type": "json_object", "keys": list(data.keys())}

            # Special handling for common kanji data structures
            if "kanji" in data and isinstance(data["kanji"], list):
                stats["kanji_count"] = len(data["kanji"])

            return stats
        else:
            return {"type": "json_primitive", "value_type": type(data).__name__}
    except Exception as e:
        return {"type": "json_file", "error": str(e)}


def get_csv_stats(csv_path: Path) -> Dict[str, Any]:
    """Get statistics from CSV file."""
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            return {"type": "csv_file", "rows": 0, "columns": 0}

        # Parse header
        header = lines[0].strip().split(",")

        return {
            "type": "csv_file",
            "rows": len(lines) - 1,  # Exclude header
            "columns": len(header),
            "headers": header,
        }
    except Exception as e:
        return {"type": "csv_file", "error": str(e)}


def analyze_file(filepath: Path, include_checksums: bool = False) -> Dict[str, Any]:
    """Analyze a single file and return metadata."""
    file_info = {
        "name": filepath.name,
        "size_bytes": filepath.stat().st_size,
        "extension": filepath.suffix.lower(),
    }

    if include_checksums:
        file_info["sha256"] = calculate_sha256(filepath)

    # Add file-type specific analysis
    if filepath.suffix.lower() == ".sqlite":
        file_info.update(get_sqlite_stats(filepath))
    elif filepath.suffix.lower() == ".json":
        file_info.update(get_json_stats(filepath))
    elif filepath.suffix.lower() == ".csv":
        file_info.update(get_csv_stats(filepath))

    return file_info


def generate_comprehensive_manifest(
    directory: Path, version: str = None, include_checksums: bool = False
) -> Dict[str, Any]:
    """Generate a comprehensive manifest for a directory."""

    manifest = {
        "version": version or "unknown",
        "generated_at": "2025-09-28",  # Could use datetime.now().isoformat()
        "directory": str(directory),
        "summary": {"total_files": 0, "total_size_bytes": 0, "file_types": {}},
        "files": [],
    }

    # Process all files in directory
    for filepath in directory.rglob("*"):
        if filepath.is_file() and filepath.name != "manifest.json":
            file_info = analyze_file(filepath, include_checksums)

            # Add relative path
            file_info["path"] = str(filepath.relative_to(directory))

            manifest["files"].append(file_info)

            # Update summary
            manifest["summary"]["total_files"] += 1
            manifest["summary"]["total_size_bytes"] += file_info["size_bytes"]

            ext = file_info["extension"]
            if ext not in manifest["summary"]["file_types"]:
                manifest["summary"]["file_types"][ext] = 0
            manifest["summary"]["file_types"][ext] += 1

    # Sort files by name for consistent ordering
    manifest["files"].sort(key=lambda x: x["path"])

    return manifest


def generate_api_manifest(directory: Path) -> Dict[str, Any]:
    """Generate API-focused manifest for web services."""
    api_manifest = {
        "api_version": "1.0",
        "description": "KANJIDIC2 derived data files",
        "endpoints": {},
    }

    # Map files to API endpoints
    for filepath in directory.rglob("*.json"):
        relative_path = filepath.relative_to(directory)
        endpoint_name = str(relative_path).replace("/", "_").replace(".json", "")

        file_stats = get_json_stats(filepath)

        api_manifest["endpoints"][endpoint_name] = {
            "file": str(relative_path),
            "size_bytes": filepath.stat().st_size,
            "description": f"Data from {filepath.stem}",
            **file_stats,
        }

    return api_manifest


def main():
    parser = argparse.ArgumentParser(
        description="Generate manifest files for kanji data directories"
    )
    parser.add_argument("--dir", "-d", required=True, help="Directory to analyze")
    parser.add_argument("--version", "-v", help="Version string for manifest")
    parser.add_argument(
        "--include-checksums",
        "-c",
        action="store_true",
        help="Include SHA256 checksums (slower)",
    )
    parser.add_argument(
        "--api-manifest",
        "-a",
        action="store_true",
        help="Also generate API-focused manifest",
    )
    parser.add_argument(
        "--output", "-o", help="Output filename (default: manifest.json)"
    )

    args = parser.parse_args()

    directory = Path(args.dir)
    if not directory.exists():
        print(f"Error: Directory {directory} does not exist")
        return

    print(f"Analyzing directory: {directory}")

    # Generate main manifest
    manifest = generate_comprehensive_manifest(
        directory, args.version, args.include_checksums
    )

    # Save main manifest
    output_file = args.output or "manifest.json"
    manifest_path = directory / output_file

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"📋 Main manifest saved: {manifest_path}")
    print(f"   - {manifest['summary']['total_files']} files")
    print(f"   - {manifest['summary']['total_size_bytes']:,} bytes total")
    print(f"   - File types: {', '.join(manifest['summary']['file_types'].keys())}")

    # Generate API manifest if requested
    if args.api_manifest:
        api_manifest = generate_api_manifest(directory)
        api_path = directory / "api_manifest.json"

        with open(api_path, "w", encoding="utf-8") as f:
            json.dump(api_manifest, f, indent=2, ensure_ascii=False)

        print(f"🌐 API manifest saved: {api_path}")
        print(f"   - {len(api_manifest['endpoints'])} API endpoints")

    if args.include_checksums:
        print("✅ SHA256 checksums included")


if __name__ == "__main__":
    main()
