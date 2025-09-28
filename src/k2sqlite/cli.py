from __future__ import annotations
import argparse
from pathlib import Path
from .builder import build_sqlite


def app():
    ap = argparse.ArgumentParser(prog="k2sqlite")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_build = sub.add_parser("build", help="Build SQLite from KANJIDIC2.xml")
    ap_build.add_argument("--input", "-i", type=Path, required=True)
    ap_build.add_argument("--db", "-o", type=Path, required=True)
    ap_build.add_argument("--batch", "-b", type=int, default=500)

    args = ap.parse_args()
    if args.cmd == "build":
        total = build_sqlite(args.input, args.db, batch_size=args.batch)
        print(f"Inserted {total} characters into {args.db}")
