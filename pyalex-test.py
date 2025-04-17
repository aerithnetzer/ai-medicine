import requests
import json
import time
import os

# Output file
output_file = "openalex_medicine_ai_works.json"

# Base URL and filter for Medicine + (AI or Deep Learning)
BASE_URL = "https://api.openalex.org/works"
FILTER = "concepts.id:C71924100,concepts.id:C119857082"

# Params for the API call
params = {
    "filter": FILTER,
    "per-page": 200,
    "cursor": "*",  # Start from beginning
    "mailto": os.getenv("EMAIL"),  # Optional but recommended
}

# Resume support: Load existing data if file exists
if os.path.exists(output_file):
    with open(output_file, "r", encoding="utf-8") as f:
        all_works = json.load(f)
else:
    all_works = []

print(f"Starting download. {len(all_works)} works already saved...")

while True:
    response = requests.get(BASE_URL, params=params)
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        break

    data = response.json()
    results = data.get("results", [])

    new_records = []
    for work in results:
        record = {
            "title": work.get("title"),
            "publication_year": work.get("publication_year"),
            "cited_by_count": work.get("cited_by_count"),
            "authors": [
                {
                    "name": author.get("author", {}).get("display_name"),
                    "id": author.get("author", {}).get("id"),
                    "orcid": author.get("author", {}).get("orcid"),
                }
                for author in work.get("authorships", [])
            ],
        }
        new_records.append(record)

    all_works.extend(new_records)

    # Save after each page
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_works, f, indent=2)

    print(f"Saved {len(new_records)} new records (total: {len(all_works)}).")

    # Get next cursor
    next_cursor = data.get("meta", {}).get("next_cursor")
    if not next_cursor:
        print("No more pages.")
        break

    params["cursor"] = next_cursor
    time.sleep(1)  # Be respectful to the API

print("Finished.")
