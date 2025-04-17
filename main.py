from metapub import PubMedFetcher
from time import sleep

query_string = "Machine Leaning[MJR]"

fetch = PubMedFetcher()

start_count = 30294
retmax_count = 500
articles = []
# Scary!!!
while True:
    articles_batch = fetch.pmids_for_query(
        query_string, retstart=start_count, retmax=retmax_count, pmc_only=True
    )
    if articles_batch:
        print("Success")
    articles.append(articles_batch)
    with open("pmidsmeta.txt", "a") as f:
        for pmid_batch in articles:
            for pmid in pmid_batch:
                line = str(pmid) + "\n"
                f.write(line)
    if articles_batch is not None:
        start_count += 500
        sleep(5)
        continue
    else:
        break
