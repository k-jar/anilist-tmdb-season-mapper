"""
AniList to TMDB Season ID Mapper

Main entry point for the season mapping tool. Provides CLI interface for
processing single IDs or batch operations.

Usage:
    python main.py
"""

import os
import json
import time
import sys
from typing import List, Tuple, Optional
from dotenv import load_dotenv
from mapper import SeasonMapper


def load_api_key() -> str:
    """
    Load TMDB API key from environment variables.

    Returns:
        TMDB API key string

    Raises:
        SystemExit: If API key is not found
    """
    load_dotenv()
    api_key = os.getenv("TMDB_API_KEY")

    if not api_key:
        print("❌ Error: TMDB_API_KEY not found in .env file.")
        print("Please create a .env file with your TMDB API key:")
        print("TMDB_API_KEY=your_key_here")
        sys.exit(1)

    return api_key


def save_results(results: List[dict], filename: str = "results.json") -> None:
    """
    Save mapping results to a JSON file.

    Args:
        results: List of mapping dictionaries
        filename: Output filename (default: results.json)
    """
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Saved {len(results)} matches to {filename}")


def load_ids_from_file(filename: str = "input_ids.txt") -> List[Tuple[int, None]]:
    """
    Load AniList IDs from a text file.

    Args:
        filename: Path to file containing IDs (one per line)

    Returns:
        List of tuples (anilist_id, None) for processing

    Raises:
        FileNotFoundError: If input file doesn't exist
    """
    with open(filename, "r", encoding="utf-8") as f:
        # Parse non-empty lines as integers, skip invalid lines
        ids = []
        for line_num, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped:
                continue
            if not stripped.isdigit():
                print(f"⚠️  Warning: Skipping invalid ID on line {line_num}: {stripped}")
                continue
            ids.append(int(stripped))

        return [(uid, None) for uid in ids]


def process_custom_file(mapper: SeasonMapper) -> List[dict]:
    """
    Process IDs from input_ids.txt file.

    Args:
        mapper: Configured SeasonMapper instance

    Returns:
        List of successful matches
    """
    try:
        tasks = load_ids_from_file()
        print(f"📄 Loaded {len(tasks)} IDs from input_ids.txt")
    except FileNotFoundError:
        print("❌ Error: input_ids.txt not found.")
        print("Create a file named 'input_ids.txt' with one AniList ID per line.")
        return []

    return process_tasks(mapper, tasks)


def process_full_database(mapper: SeasonMapper) -> List[dict]:
    """
    Process all IDs from the Fribb anime-lists database.

    Args:
        mapper: Configured SeasonMapper instance

    Returns:
        List of successful matches
    """
    confirm = input(
        "⚠️  This process may take hours. Continue? (y/n): "
    )
    if confirm.lower() != "y":
        print("Operation cancelled.")
        return []

    full_map = mapper.load_mapping_data()
    tasks = list(full_map.items())
    print(f"📊 Prepared to process {len(tasks)} items from database.")

    return process_tasks(mapper, tasks)


def process_tasks(
    mapper: SeasonMapper, tasks: List[Tuple[int, Optional[int]]]
) -> List[dict]:
    """
    Process a list of AniList IDs and return successful matches.

    Args:
        mapper: Configured SeasonMapper instance
        tasks: List of (anilist_id, tmdb_id) tuples

    Returns:
        List of successful match dictionaries
    """
    results = []
    processed_ids = set()

    # Load existing results to skip processed IDs
    if os.path.exists("results.json"):
        try:
            with open("results.json", "r", encoding="utf-8") as f:
                results = json.load(f)
                processed_ids = {item.get("anilist_id") for item in results if item.get("anilist_id")}
        except Exception:
            pass

    tasks = [t for t in tasks if t[0] not in processed_ids]
    total = len(tasks)

    if total == 0:
        print("No new tasks to process.")
        return results

    print(f"\n🚀 Starting processing of {total} items...")
    print("=" * 60)

    initial_count = len(results)

    try:
        for index, (anilist_id, tmdb_id) in enumerate(tasks):
            # Progress indicator every 10 items
            if index % 10 == 0 and index > 0:
                new_matches = len(results) - initial_count
                success_rate = new_matches / index * 100 if index > 0 else 0
                print(f"📊 Progress: {index}/{total} ({success_rate:.1f}% match rate)")

            match = mapper.process_id(anilist_id, tmdb_id)
            if match:
                results.append(match)

            # Rate limiting
            # AniList: 90 requests/min, TMDB: generally permissive
            # AniList temporary 30 request/min rate limit
            time.sleep(2.1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user.")
        print(f"Processed {index + 1}/{total} items before interruption.")

    print("=" * 60)
    print(
        f"✅ Processing complete: {len(results)} successful matches out of {total} attempts"
    )

    return results


def display_menu() -> str:
    """
    Display the main menu and get user choice.

    Returns:
        User's menu selection as string
    """
    print("\n" + "=" * 60)
    print("         AniList to TMDB Season ID Mapper")
    print("=" * 60)
    print("1. Process IDs from input_ids.txt")
    print("2. Process ALL IDs from Fribb Mapping (⚠️  Takes hours)")
    print("=" * 60)

    return input("Enter choice (1 or 2): ").strip()


def main() -> None:
    """
    Main application entry point.

    Handles CLI interaction, processing coordination, and result saving.
    """
    # Load configuration
    api_key = load_api_key()
    mapper = SeasonMapper(api_key)

    # Display menu and get choice
    choice = display_menu()

    # Process based on user selection
    if choice == "1":
        results = process_custom_file(mapper)
    elif choice == "2":
        results = process_full_database(mapper)
    else:
        print("❌ Invalid choice. Please enter 1 or 2.")
        return

    # Save results if any were found
    if results:
        save_results(results)
    else:
        print("\n⚠️  No matches found. No output file created.")


if __name__ == "__main__":
    main()
