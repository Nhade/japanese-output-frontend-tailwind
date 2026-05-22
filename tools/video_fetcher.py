"""
CLI tool for batch-importing YouTube videos into the Shiori database.

Usage:
  python tools/video_fetcher.py URL [URL ...]
  python tools/video_fetcher.py --file urls.txt
"""
import argparse
import sys

from config import settings
from logging_config import configure_logging

# Backend modules log via the `logging` module. Configure before importing
# video_service because its dependency graph may log during client setup.
configure_logging()

DATABASE_PATH = str(settings.database_path)


def main():
    from video_service import import_video

    parser = argparse.ArgumentParser(description="Import YouTube videos for Japanese learning exercises")
    parser.add_argument("urls", nargs="*", help="YouTube URLs to import")
    parser.add_argument("--file", "-f", help="Path to a text file with one URL per line")
    parser.add_argument("--whisper", action="store_true",
                        help="Transcribe audio via OpenAI Whisper instead of YouTube captions")
    args = parser.parse_args()

    urls = list(args.urls)

    if args.file:
        with open(args.file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)

    if not urls:
        parser.print_help()
        print("\nError: No URLs provided.")
        sys.exit(1)

    print(f"Importing {len(urls)} video(s){'  [Whisper ASR]' if args.whisper else ''}...\n")

    success = 0
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")
        try:
            result = import_video(url, DATABASE_PATH, use_whisper=args.whisper)
            status = "already existed" if result.get("already_exists") else "imported"
            print(f"  -> {status}: {result['title']} (ID: {result['video_id']})\n")
            success += 1
        except Exception as e:
            print(f"  -> FAILED: {e}\n")

    print(f"\nDone. {success}/{len(urls)} videos imported successfully.")


if __name__ == "__main__":
    main()
