import plotly.graph_objects as go
import json
from collections import defaultdict
from statistics import mean, median
import pprint

# Load data
with open("./openalex_medicine_ai_works.json", "r", encoding="utf-8") as f:
    works = json.load(f)

# Group citation counts by year
citations_by_year = defaultdict(list)
for work in works:
    year = work.get("publication_year")
    citations = work.get("cited_by_count", 0)
    if year:
        citations_by_year[year].append(citations)

# Compute average and median citation counts by year
citation_stats = {
    year: {
        "average": mean(cites),
        "median": median(cites),
        "count": len(cites),
    }
    for year, cites in citations_by_year.items()
}

# Add normalized citation score to each work
for work in works:
    current_year = 2025
    year = work.get("publication_year")
    citations = work.get("cited_by_count", 0)
    if year in citation_stats and citation_stats[year]["average"] > 0:
        work["normalized_citation_score"] = citations / current_year - int(year) + 1
    else:
        work["normalized_citation_score"] = None  # fallback for odd data

# Sort works by normalized citation score (descending)
ranked = sorted(
    [w for w in works if w["normalized_citation_score"] is not None],
    key=lambda x: x["normalized_citation_score"],
    reverse=True,
)

# Print top 10 high-impact works (adjusted for age)
print("\nTop 10 High-Impact Works (Normalized Citation Score):\n")
for i, work in enumerate(ranked[:10], 1):
    print(f"{i}. {work['title'][:80]}...")
    print(
        f"   Year: {work['publication_year']}, Citations: {work['cited_by_count']}, Normalized: {work['normalized_citation_score']:.2f}"
    )
    print(
        f"   First Author: {work['authors'][0]['name'] if work['authors'] else 'Unknown'}\n"
    )
# Extract years from citation_stats
years = sorted(citation_stats.keys())

# Filter years after 2000
filtered_years = [year for year in years if year > 2000]
filtered_averages = [citation_stats[year]["average"] for year in filtered_years]
filtered_counts = [citation_stats[year]["count"] for year in filtered_years]

# Plot average normalized citation count and total articles published over years using Plotly
fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=filtered_years,
        y=filtered_averages,
        mode="lines+markers",
        name="Average Normalized Citations",
    )
)
fig.add_trace(
    go.Scatter(
        x=filtered_years,
        y=filtered_counts,
        mode="lines+markers",
        name="Total Articles Published",
        yaxis="y2",  # Use secondary y-axis
    )
)
fig.update_layout(
    title="Average Normalized Citation Count and Total Articles Published Over Years (Post-2000)",
    xaxis_title="Year",
    yaxis=dict(title="Average Normalized Citation Count"),
    yaxis2=dict(title="Total Articles Published", overlaying="y", side="right"),
    template="plotly_white",
)
fig.show()
