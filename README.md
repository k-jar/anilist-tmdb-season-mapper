# AniList to TMDB Season ID Mapper

A Python tool that maps **AniList anime IDs** to specific **TheMovieDB (TMDB) Season IDs** using a date-anchoring algorithm.

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## The Problem

AniList and TMDB structure anime differently, creating a mapping challenge:

- **AniList:** Treats each season (S1, S2, S3) as a separate database entry with a unique ID
- **TMDB:** Groups all seasons under one show entry with nested season objects
- **Granularity Gap:** Standard mapping lists like Fribb convert `AniList ID` → `TMDB Show ID`, but both S1 and S2 map to the same show ID. You lose information about which specific season you're dealing with.

### Example

```
Attack on Titan S1 (AniList: 16498) ───┐
                                       ├──> TMDB Show: 1429 (no season info!)
Attack on Titan S2 (AniList: 20958) ───┘
```

**Why This Matters:**
- You can't fetch season-specific data (posters, episode lists, air dates)
- You don't know the TMDB season number (is this S1? S2? S3?)
- You can't use season-specific endpoints like `/tv/season/{season_id}`

This tool solves the problem by providing both the **season number** and the **internal season ID**:

```
AniList 20958 → TMDB Show 1429, Season 2 (ID: 85987)
```

## The Solution

This tool implements a **date-anchor algorithm** to bridge the gap:

1. **Base Mapping:** Convert `AniList ID` → `TMDB Show ID` using [Fribb/anime-lists](https://github.com/Fribb/anime-lists)
2. **Date Retrieval:** Fetch the start date from AniList's API
3. **Season Discovery:** Fetch all seasons for the TMDB show
4. **Smart Matching:** Compare dates and select the season with the closest air date within tolerance (default: 7 days)

```python
tmdb_show_id = fribb_mapping[anilist_id]
anilist_date = get_anilist_date(anilist_id)
tmdb_seasons = get_tmdb_seasons(tmdb_show_id)

best_match = find_closest_season(anilist_date, tmdb_seasons, tolerance=7)
return best_match['id']  # The specific TMDB Season ID
```

### Handling Edge Cases

**Movies and OVAs:** When no seasons are found (indicating a movie or OVA), the mapper returns `None` for season-specific fields:

```json
{
  "anilist_id": 12345,
  "title": "Some Movie",
  "tmdb_show_id": 67890,
  "tmdb_season_id": null,
  "tmdb_season_number": null,
  "matched_date": null,
  "date_difference_days": null
}
```

This allows you to handle movies separately by checking if `tmdb_season_id` is `null`.

## Installation

### Prerequisites

- Python 3.7 or higher
- TMDB API key ([Get one here](https://www.themoviedb.org/settings/api))

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/k-jar/anilist-tmdb-season-mapper.git
   cd anilist-tmdb-season-mapper
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API key**
   
   Create a `.env` file in the project root:
   ```ini
   TMDB_API_KEY=your_api_key_here
   ```

## Usage

### Basic Usage

Run the interactive CLI:

```bash
python main.py
```

You'll be presented with two options:

1. **Process custom IDs:** Create an `input_ids.txt` file with one AniList ID per line
2. **Process full database:** Map all entries from Fribb (takes several hours)

### Example Input File

Create `input_ids.txt`:
```
1535
20958
177937
```

### Output Format

Results are saved to `results.json`:

```json
[
  {
    "anilist_id": 20958,
    "title": "Attack on Titan Season 2",
    "tmdb_show_id": 1429,
    "tmdb_season_id": 84756,
    "tmdb_season_number": 2,
    "matched_date": "2017-04-01",
    "date_difference_days": 0
  },
  {
    "anilist_id": 12345,
    "title": "Some Movie",
    "tmdb_show_id": 67890,
    "tmdb_season_id": null,
    "tmdb_season_number": null,
    "matched_date": null,
    "date_difference_days": null
  }
]
```

### Using the Season ID

With the output, you can now make precise TMDB API calls:

```bash
# Get season details
curl "https://api.themoviedb.org/3/tv/season/85987?api_key=YOUR_KEY"

# Get season images
curl "https://api.themoviedb.org/3/tv/season/85987/images?api_key=YOUR_KEY"
```

## Features

- **Smart Date Matching:** Prioritizes the closest air date match when multiple seasons fall within tolerance
- **Configurable Tolerance:** Adjust the maximum acceptable date difference (default: 7 days)
- **Date Difference Tracking:** Shows how close the match was in days
- Automatic rate limit handling (respects API quotas)
- Progress tracking and interruption handling
- Comprehensive error logging

## Limitations

- **Specials/OVAs:** Often grouped in "Season 0" with imprecise or missing air dates, may return `null` season IDs
- **Split Cours:** Anime that air in two parts may be grouped as one season on TMDB but split on AniList
- **Outdated Mappings:** The Fribb database may lag behind new releases
- **Date Mismatches:** Regional release differences can cause date discrepancies beyond the tolerance window

## Acknowledgments

- [Fribb/anime-lists](https://github.com/Fribb/anime-lists) for the base mapping data
- [AniList](https://anilist.co/) and [TheMovieDB](https://www.themoviedb.org/) for their public APIs