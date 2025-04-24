import requests
import time
import json
import os
import argparse
from urllib.parse import quote_plus
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("pmc_search.log"), logging.StreamHandler()],
)
logger = logging.getLogger()


class PMCSearcher:
    def __init__(self, email, api_key=None, tool="pmc_ml_med_search"):
        """
        Initialize the PMC searcher with your identification

        Parameters:
        - email: Your email address (required by NCBI)
        - api_key: Your NCBI API key (optional, but recommended for higher rate limits)
        - tool: Name of your tool/script
        """
        self.email = email
        self.api_key = api_key
        self.tool = tool
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        self.search_url = f"{self.base_url}esearch.fcgi"
        self.fetch_url = f"{self.base_url}efetch.fcgi"
        self.summary_url = f"{self.base_url}esummary.fcgi"
        self.link_url = f"{self.base_url}elink.fcgi"

    def _get_common_params(self):
        """Return common parameters for all API requests"""
        params = {"email": self.email, "tool": self.tool, "retmode": "json"}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def search(self, query, db="pmc", retmax=100, retstart=0):
        """
        Search PubMed Central with the given query

        Parameters:
        - query: Search query string
        - db: Database to search (default: pmc)
        - retmax: Maximum number of results to return (default: 100)
        - retstart: Index of first result to return (for pagination)

        Returns:
        - Dictionary with search results
        """
        params = self._get_common_params()
        params.update(
            {
                "db": db,
                "term": query,
                "retmax": retmax,
                "retstart": retstart,
                "usehistory": "y",  # Use history to allow retrieving large result sets
            }
        )

        response = requests.get(self.search_url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    def fetch_article_details(
        self,
        id_list=None,
        db="pmc",
        webenv=None,
        query_key=None,
        retstart=0,
        retmax=100,
    ):
        """
        Fetch detailed information for a list of article IDs or using WebEnv and QueryKey

        Parameters:
        - id_list: List of PMC IDs (optional if using webenv+query_key)
        - db: Database to fetch from (default: pmc)
        - webenv: WebEnv value from search results (for history server)
        - query_key: QueryKey value from search results
        - retstart: Index of first result to return (for pagination)
        - retmax: Maximum number of results to return

        Returns:
        - Dictionary with article details
        """
        params = self._get_common_params()
        params.update({"db": db, "retmax": retmax, "retstart": retstart})

        if id_list:
            params["id"] = ",".join(id_list)
        elif webenv and query_key:
            params["webenv"] = webenv
            params["query_key"] = query_key
        else:
            return {"error": "No IDs or WebEnv+QueryKey provided"}

        response = requests.get(self.summary_url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    def fetch_full_text(self, pmc_id, output_format="xml"):
        """
        Fetch the full text of an article by PMC ID

        Parameters:
        - pmc_id: PMC ID of the article
        - output_format: Format for the full text (xml, pdf, etc.)

        Returns:
        - Full text content
        """
        params = self._get_common_params()
        params.update({"db": "pmc", "id": pmc_id})

        # For full text, we need different retmode handling
        if output_format == "xml":
            params["retmode"] = "xml"

        response = requests.get(self.fetch_url, params=params)

        # Check if it's a valid response
        if response.status_code == 200:
            # Check if it's actually XML content and not an error
            if output_format == "xml" and "<!DOCTYPE html" in response.text[:100]:
                raise Exception(
                    "Received HTML instead of XML - article might not be available in PMC"
                )
            return response.content
        else:
            response.raise_for_status()

    def get_pubmed_to_pmc_links(self, pubmed_ids):
        """Convert PubMed IDs to PMC IDs where available"""
        params = self._get_common_params()
        params.update({"dbfrom": "pubmed", "db": "pmc", "id": ",".join(pubmed_ids)})

        response = requests.get(self.link_url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()

    def search_mesh_terms(
        self, mesh_terms, logical_operator="AND", retmax=100, retstart=0
    ):
        """
        Search for articles with specific MeSH terms

        Parameters:
        - mesh_terms: List of MeSH terms
        - logical_operator: How to combine terms ("AND" or "OR")
        - retmax: Maximum number of results per query
        - retstart: Start index for pagination

        Returns:
        - Search results
        """
        # Format each term as a MeSH query
        mesh_queries = [f'"{term}"[mesh]' for term in mesh_terms]

        # Join with the logical operator
        query = f" {logical_operator} ".join(mesh_queries)

        return self.search(query, retmax=retmax, retstart=retstart)


def search_ml_medicine_articles(
    email, api_key=None, batch_size=500, output_file="ml_medicine_articles.json"
):
    """
    Search for articles that have both machine learning and medicine MeSH tags
    Implements pagination to get ALL results

    Parameters:
    - email: Your email for NCBI
    - api_key: Your NCBI API key (optional)
    - batch_size: Number of results to fetch per request
    - output_file: File to save results
    """
    searcher = PMCSearcher(email=email, api_key=api_key)

    # Define MeSH terms for machine learning and medicine
    ml_terms = [
        "Artificial Intelligence",
    ]

    # We'll store all articles here, keyed by PMC ID to avoid duplicates
    all_articles = {}

    progress_file = "search_progress.json"
    # Check if we have a progress file to resume from
    try:
        with open(progress_file, "r") as f:
            progress_data = json.load(f)
            searched_combos = progress_data.get("searched_combos", [])
            all_articles = progress_data.get("articles", {})
            logger.info(
                f"Resuming from progress file. {len(searched_combos)} combinations already searched."
            )
    except (FileNotFoundError, json.JSONDecodeError):
        searched_combos = []
        logger.info("Starting new search.")

    # Generate all combinations of ML and medicine terms
    term_combinations = []
    for ml_term in ml_terms:
        term_combinations.append((ml_term))

    # Process each combination
    for ml_term in ml_terms:
        # Skip if we've already searched this combination
        combo_key = f"{ml_term}"
        if combo_key in searched_combos:
            logger.info(f"Skipping already processed combination: {ml_term}")
            continue

        query = f"{ml_term}"
        logger.info(f"Searching for: {query}")

        # First, get the count of results
        initial_results = searcher.search(query, retmax=0)

        if (
            "esearchresult" in initial_results
            and "count" in initial_results["esearchresult"]
        ):
            total_results = int(initial_results["esearchresult"]["count"])
            logger.info(f"Found {total_results} total articles for {ml_term}")

            # Get WebEnv and QueryKey for efficient retrieval
            webenv = initial_results["esearchresult"].get("webenv")
            query_key = initial_results["esearchresult"].get("querykey")

            if webenv and query_key:
                # Fetch results in batches
                for start in range(0, total_results, batch_size):
                    retmax = min(batch_size, total_results - start)
                    logger.info(
                        f"Fetching batch {start + 1}-{start + retmax} of {total_results}"
                    )

                    try:
                        # Get article IDs for this batch
                        search_batch = searcher.search(
                            query, retmax=retmax, retstart=start
                        )

                        if (
                            "esearchresult" in search_batch
                            and "idlist" in search_batch["esearchresult"]
                        ):
                            id_list = search_batch["esearchresult"]["idlist"]

                            if id_list:
                                # Get details for these IDs
                                details = searcher.fetch_article_details(id_list)

                                if "result" in details:
                                    # Add articles to our collection
                                    for article_id, article_data in details[
                                        "result"
                                    ].items():
                                        if article_id != "uids":
                                            all_articles[article_id] = article_data

                        # Save progress after each batch
                        searched_combos.append(combo_key)
                        with open(progress_file, "w") as f:
                            json.dump(
                                {
                                    "searched_combos": searched_combos,
                                    "articles": all_articles,
                                },
                                f,
                            )

                        # Respect API rate limits
                        time.sleep(0.34)  # Max 3 requests per second

                    except Exception as e:
                        logger.error(f"Error processing batch starting at {start}: {e}")
                        # Save progress before exiting loop
                        with open(progress_file, "w") as f:
                            json.dump(
                                {
                                    "searched_combos": searched_combos,
                                    "articles": all_articles,
                                },
                                f,
                            )
            else:
                logger.warning(f"WebEnv or QueryKey missing for {ml_term}")
        else:
            logger.warning(f"Could not get count for {ml_term}")

        # Mark this combination as completed
        searched_combos.append(combo_key)

        # Save progress after each term combination
        with open(progress_file, "w") as f:
            json.dump({"searched_combos": searched_combos, "articles": all_articles}, f)

    # Convert to list for final output
    article_list = list(all_articles.values())
    logger.info(f"Found {len(article_list)} unique articles across all searches")

    # Save to file
    with open(output_file, "w") as f:
        json.dump(article_list, f, indent=2)

    logger.info(f"Results saved to {output_file}")
    return all_articles


def download_full_texts(
    articles, email, api_key=None, output_dir="full_texts", resume=True
):
    """
    Download full texts for all articles

    Parameters:
    - articles: Dictionary of article data from search_ml_medicine_articles
    - email: Your email for NCBI
    - api_key: Your NCBI API key (optional)
    - output_dir: Directory to save full texts
    - resume: Whether to skip articles that have already been downloaded
    """
    searcher = PMCSearcher(email=email, api_key=api_key)

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Track progress
    download_progress_file = "download_progress.json"

    # Load progress if resuming
    downloaded_ids = set()
    if resume:
        try:
            with open(download_progress_file, "r") as f:
                downloaded_ids = set(json.load(f))
                logger.info(
                    f"Resuming downloads. {len(downloaded_ids)} articles already downloaded."
                )
        except (FileNotFoundError, json.JSONDecodeError):
            logger.info("No existing download progress found. Starting fresh.")

    # Count for progress tracking
    total_articles = len(articles)
    completed = 0

    for article_id, article in articles.items():
        if article_id == "uids":
            continue

        # Skip if already downloaded
        if article_id in downloaded_ids:
            logger.info(f"Skipping already downloaded article: PMC{article_id}")
            completed += 1
            continue

        title = article.get("title", "Untitled")
        logger.info(
            f"[{completed + 1}/{total_articles}] Downloading: {title} (PMC{article_id})"
        )

        try:
            full_text = searcher.fetch_full_text(article_id)

            # Save to file
            filename = os.path.join(output_dir, f"PMC{article_id}.xml")
            with open(filename, "wb") as f:
                f.write(full_text)

            logger.info(f"Saved to {filename}")

            # Update progress
            downloaded_ids.add(article_id)
            with open(download_progress_file, "w") as f:
                json.dump(list(downloaded_ids), f)

            # Respect API rate limits
            time.sleep(0.34)

        except Exception as e:
            logger.error(f"Error downloading PMC{article_id}: {e}")

        completed += 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Search PubMed Central for ALL machine learning and medicine articles"
    )
    parser.add_argument(
        "--email", required=True, help="Your email address (required by NCBI)"
    )
    parser.add_argument(
        "--api-key", help="Your NCBI API key (optional, but recommended)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of results to fetch per batch",
    )
    parser.add_argument(
        "--output",
        default="ml_medicine_articles.json",
        help="Output file for article metadata",
    )
    parser.add_argument("--download", action="store_true", help="Download full texts")
    parser.add_argument(
        "--output-dir", default="full_texts", help="Directory for full texts"
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start fresh, don't resume from previous progress",
    )

    args = parser.parse_args()

    # Search for articles
    articles = search_ml_medicine_articles(
        email=args.email,
        api_key=args.api_key,
        batch_size=args.batch_size,
        output_file=args.output,
    )

    # Download full texts if requested
    if args.download:
        download_full_texts(
            articles=articles,
            email=args.email,
            api_key=args.api_key,
            output_dir=args.output_dir,
            resume=not args.no_resume,
        )
