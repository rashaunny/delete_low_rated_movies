import os
import re
import argparse
import requests
from pathlib import Path

# === CONFIGURATION ===

# Placeholder for TMDb API Key (user must input their own)
TMDB_API_KEY = "5d492845372e8c4e96ac12c0f3969738"

# Minimum IMDb rating threshold
RATING_THRESHOLD = 6.0

# Supported video file extensions
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov'}

# TMDb Search and Details API endpoints
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_DETAILS_URL = "https://api.themoviedb.org/3/movie/{}"

# Regex to remove unwanted info from filenames
CLEANUP_REGEX = re.compile(
    r"(1080p|720p|480p|x264|x265|XviD|BluRay|BRRip|DVDRip|HDRip|WEBRip|YIFY|KLAXXON|VoMiT|Newmyvideolinks|Myvideolinks|\[.*?\])",
    re.IGNORECASE
)

# Regex to match year and truncate anything after it
YEAR_CUTOFF_REGEX = re.compile(r"(.*?)\b(\d{4})\b")

# === CORE FUNCTIONS ===


def clean_title(filename):
    name = Path(filename).stem
    name = name.replace('.', ' ').replace('_', ' ').replace('-', ' ')
    name = CLEANUP_REGEX.sub('', name)
    name = re.sub(r'\s+', ' ', name).strip()

    # Truncate at the first 4-digit year and discard anything after
    match = re.search(r'\b(\d{4})\b', name)
    if match:
        cutoff_index = match.end()
        name = name[:cutoff_index].strip()

    # Remove stray parentheses that may be left around the year
    name = re.sub(r'[()]', '', name).strip()

    return name

# Updated query_tmdb function that now accepts year as a parameter
def query_tmdb(title, year=None):
    params = {
        "api_key": TMDB_API_KEY,
        "query": title,
    }
    if year:
        params["year"] = year  # Pass the year as a parameter if it's available

    try:
        response = requests.get(TMDB_SEARCH_URL, params=params)
        data = response.json()
        if data["results"]:
            movie = data["results"][0]
            movie_id = movie["id"]
            details = requests.get(TMDB_DETAILS_URL.format(
                movie_id), params={"api_key": TMDB_API_KEY}).json()
            return details.get("vote_average", 0.0)
    except Exception as e:
        print(f"Error querying TMDb for {title}: {e}")
    return None


def find_movies_to_delete(folder_path):
    to_delete = []

    for root, _, files in os.walk(folder_path):
        for file in files:
            # Only video files in declaration
            if Path(file).suffix.lower() not in VIDEO_EXTENSIONS:
                continue

            # Skip if 'sample' or 'trailer' in filename
            if re.search(r'\b(sample|trailer)\b', file, re.IGNORECASE):
                continue

            path = os.path.join(root, file)
            title = clean_title(file)

            # Extract year if possible
            year_match = re.search(r'\b(\d{4})\b', title)
            year = year_match.group(1) if year_match else None

            # If a year is found, remove it from the title for querying
            if year:
                title_without_year = title.replace(year, '').strip()
            else:
                title_without_year = title

            # Debugging output: Check if the year is being stripped from the title
            print(
                f"Trying to query for title: {title_without_year} with year: {year}")

            # Query TMDb with title and year (if available)
            rating = query_tmdb(title_without_year, year)

            if rating is not None:
                if rating == 0:
                    print(f"Skipping {title} (False 0 IMDb rating :/)")
                    continue  # Skip files with a 0 rating, as they are not reliable
                print(f"Found: {title} : Rating: {rating}")
                if rating < RATING_THRESHOLD:
                    to_delete.append((path, title, rating))
            else:
                print(f"Could not find rating for: {file} -> Tried: {title}")

    return to_delete


def main():
    parser = argparse.ArgumentParser(
        description="Delete movies with IMDb rating below a threshold.")
    parser.add_argument("path", help="Path to scan for movies")
    parser.add_argument("--dry", action="store_true",
                        default=True, help="Perform a dry run (default)")

    args = parser.parse_args()
    results = find_movies_to_delete(args.path)

    if not results:
        print("No movies found below the rating threshold.")
        return

    for path, title, rating in results:
        if args.dry:
            print(f"[Dry Run] Would delete: {title} ({rating}) - {path}")
        else:
            try:
                os.remove(path)
                print(f"Deleted: {path}")
            except Exception as e:
                print(f"Failed to delete {path}: {e}")


if __name__ == "__main__":
    main()
