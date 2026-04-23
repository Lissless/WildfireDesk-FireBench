from build.lib.llmproxy import LLMProxy
import datetime
from os import walk
import requests
import json
import ast
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from requests.exceptions import RequestException, Timeout
import re

### ----------------------------------------------------------------------------------------------------
### System Settings
### ----------------------------------------------------------------------------------------------------

timestamp_format = "%Y-%m-%d_%H-%M-%S"
timestamp = datetime.datetime.now().strftime(timestamp_format)
timestamp_stale_allowance = 1
crawl_depth = 1
SUMMARIZE = 0
SEARCH = 1
verbose = True
crawl_time = ""
news_resources = "sage-resources/web-crawl-data"
news_region_resources = "sage-resources/state-local-news-outlets"
selected_state = "California"
selected_community = "Bay Area"
conduct_internet_search = True

request_timeout_seconds = 8
max_links_per_page = 15
max_content_chars = 50000

# apparently we need this so sites don't block our request right away when crawling
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

### ----------------------------------------------------------------------------------------------------
### Ivy Settings
### ----------------------------------------------------------------------------------------------------

ivy = LLMProxy()
ivy_model = "gemini-2.5-flash-lite"
ivy_html_system = (
    "You will receive the raw HTML of a webpage and user input in the format "
    "HTML:<HTML> UserInput:<usr>. Extract the key findings from the webpage "
    "that are related to the user input. Respond briefly and clearly."
)
ivy_discern_system = "respond in the format: <Yes or No>|<reason why>"
ivy_url_classify_system = """Respond ONLY with a single Python dictionary in this exact format:
    {1:True, 2:False, 3:True}
    Do not include explanation.
    Do not repeat the dictionary.
    Do not include any extra text."""
ivy_session_id = "ivy" + str(timestamp)
ivy_temperature = 0.2

session = requests.Session()
session.headers.update(DEFAULT_HEADERS)

### ----------------------------------------------------------------------------------------------------
### Request and Response Helper Functions
### ----------------------------------------------------------------------------------------------------

# function: safe_get
# fetches a page and skips timeouts, non-200 responses, and non-html content
def safe_get(url, timeout=request_timeout_seconds):
    try:
        response = session.get(url, timeout=timeout, allow_redirects=True)
    except Timeout:
        print("Timed out while fetching:", url)
        return None
    except RequestException as e:
        print("Request failed for", url, ":", e)
        return None

    if response.status_code != 200:
        print("Skipping non-200 response:", response.status_code, url)
        return None

    content_type = response.headers.get("Content-Type", "").lower()
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        print("Skipping non-html response:", content_type, url)
        return None

    return response


# function: prompt_ivy
# sends a prompt to ivy and returns the model response
def prompt_ivy(query_prompt, ivy_sys):
    response = ivy.generate(
        model=ivy_model,
        system=ivy_sys,
        query=query_prompt,
        temperature=ivy_temperature,
        session_id=ivy_session_id,
    )
    return response


# function: extract_response_string
# pulls the text result out of ivy's response format
def extract_response_string(response):
    if isinstance(response, dict):
        res = response.get("result")
    elif isinstance(response, tuple):
        res = response[0]["result"]
    else:
        res = response
    return res


# function: extract_dict_from_response
# finds and parses a python dictionary from model output
def extract_dict_from_response(resp_str):
    start_positions = [i for i, ch in enumerate(resp_str) if ch == "{"]

    for start in start_positions:
        depth = 0
        for i in range(start, len(resp_str)):
            if resp_str[i] == "{":
                depth += 1
            elif resp_str[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = resp_str[start:i + 1]
                    try:
                        return ast.literal_eval(candidate)
                    except Exception:
                        break

    return None

### ----------------------------------------------------------------------------------------------------
### State, Community, and Path Helper Functions
### ----------------------------------------------------------------------------------------------------

# function: normalize_community_name
# normalizes missing or dashed community names to general
def normalize_community_name(raw_value):
    if raw_value is None:
        return "General"

    value = str(raw_value).strip()

    if not value:
        return "General"

    if value.count("-") == len(value):
        return "General"

    return value


# function: make_safe_filename
# converts an outlet name into a safe filename
def make_safe_filename(name):
    if not name:
        return "unknown_outlet"

    safe = name.strip()
    safe = safe.replace("&", "and")
    safe = safe.replace("/", "_")
    safe = safe.replace("\\", "_")
    safe = re.sub(r"\s+", "_", safe)
    safe = re.sub(r"[^A-Za-z0-9._-]", "", safe)
    safe = re.sub(r"_+", "_", safe).strip("._-")

    return safe or "unknown_outlet"


# function: get_outlet_cache_path
# builds the cache file path for one outlet
def get_outlet_cache_path(outlet_name):
    safe_name = make_safe_filename(outlet_name)
    return f"{news_resources}/{safe_name}.jsonl"


# function: get_all_supported_states
# returns all supported states from the outlet files
def get_all_supported_states():
    states = []
    for (_, _, filenames) in walk(news_region_resources):
        for file in filenames:
            fname = file.replace("_", " ")
            state_name = fname.split(".")[0]
            states.append(state_name)
        break
    return states


# function: get_all_supported_communities
# returns all supported communities for one state
def get_all_supported_communities(state):
    communities = set()
    state_file = f"{news_region_resources}/{state}.jsonl"

    with open(state_file, "r", encoding="utf-8") as infile:
        for line in infile:
            record = json.loads(line)
            com = record["Community"]
            if com.count("-") != len(com):
                communities.add(com)
            else:
                communities.add("General")

    return list(communities)


# function: get_state_to_communities_map
# builds a map of each state to its supported communities
def get_state_to_communities_map():
    state_map = {}

    for (_, _, filenames) in walk(news_region_resources):
        for file in filenames:
            if not file.endswith(".jsonl"):
                continue

            state_name = file.replace("_", " ").replace(".jsonl", "")
            state_file = f"{news_region_resources}/{file}"

            communities = set()

            with open(state_file, "r", encoding="utf-8") as infile:
                for line in infile:
                    record = json.loads(line)
                    community = normalize_community_name(record.get("Community"))
                    communities.add(community)

            state_map[state_name] = sorted(communities)
        break

    return state_map


# function: get_all_unique_communities
# returns all unique communities across every state
def get_all_unique_communities():
    all_communities = set()
    state_map = get_state_to_communities_map()

    for communities in state_map.values():
        all_communities.update(communities)

    return sorted(all_communities)

### ----------------------------------------------------------------------------------------------------
### Crawl Data and Cache Functions
### ----------------------------------------------------------------------------------------------------

# function: get_root
# reads the first cached record for an outlet
def get_root(root_name):
    try:
        name = get_outlet_cache_path(root_name)
        print("getting root of name: ", name)

        with open(name, "r", encoding="utf-8") as crawl_file:
            first_line = crawl_file.readline().strip()
            if not first_line:
                return None
            root = json.loads(first_line)

        print("get root root: ", root)
        return root
    except Exception:
        print("Failed get root open")
        return None


# function: get_crawl_record
# looks up one cached record by url
def get_crawl_record(url, root_name):
    try:
        with open(get_outlet_cache_path(root_name), "r", encoding="utf-8") as crawl_file:
            line = crawl_file.readline()
            while line:
                record = json.loads(line)
                if record["URL"] == url:
                    return record
                line = crawl_file.readline()
    except Exception:
        return None

    return None


# function: get_all_crawl_data
# loads cached crawl records and can filter by community
def get_all_crawl_data(filename, community=None):
    res = []
    try:
        with open(filename, "r", encoding="utf-8") as crawl_file:
            line = crawl_file.readline()

            while line:
                record = json.loads(line)

                if community is not None:
                    record_community = normalize_community_name(record.get("Community"))
                    target_community = normalize_community_name(community)

                    if record_community != target_community:
                        line = crawl_file.readline()
                        continue

                    record["Community"] = record_community

                res.append(record)
                line = crawl_file.readline()

    except Exception as e:
        print("get all crawl data bad exit:", e)
        return res

    return res


# function: get_summaries_list
# builds a numbered list of cached summaries for ivy to rank
def get_summaries_list(filename):
    summary_text = ""
    idx = 1

    try:
        with open(filename, "r", encoding="utf-8") as crawl_file:
            line = crawl_file.readline()
            while line:
                record = json.loads(line)
                summary = record.get("Summary", "").strip()
                if summary:
                    summary_text += f"{idx}. {summary}\n"
                    idx += 1
                line = crawl_file.readline()
                print("Looking at record number: ", idx)
    except Exception:
        return summary_text

    return summary_text


# function: redo_crawl_check
# decides if cached crawl data is stale and should be refreshed
def redo_crawl_check(record, current_time_str):
    if record is None:
        return True

    record_time = datetime.datetime.strptime(record["Timestamp"], timestamp_format)
    current_time = datetime.datetime.strptime(current_time_str, timestamp_format)
    diff = current_time - record_time

    return diff.days >= timestamp_stale_allowance


# function: add_summary
# adds outlet summaries to the summary file for a state
def add_summary(state, move_ahead=0):
    input_file = f"sage-resources/state-local-news-outlets/{state}.jsonl"
    output_file = f"sage-resources/state-local-news-summaries/{state}.jsonl"
    retry = 2
    failed = []

    with open(input_file, "r", encoding="utf-8") as infile, open(output_file, "a", encoding="utf-8") as outfile:
        skip = 0

        for line in infile:
            if skip != move_ahead:
                skip += 1
                print("Skip: ", skip)
                continue

            record = json.loads(line)
            url = record.get("Website", "")
            local_retry = retry
            success = False

            if "http" in url:
                while local_retry != 0:
                    page = safe_get(url)
                    if page is None:
                        local_retry -= 1
                        print("Retry: ", local_retry)
                        continue

                    try:
                        html_content = extract_html_content(page.text)
                        ivy_prompt = (
                            f"HTML:{html_content} UserInput: Summarize the content of this webpage in 4 sentences. "
                            "Mention the main topic, key words and any social groups of people it mentions."
                        )
                        resp = prompt_ivy(ivy_prompt, ivy_html_system)
                        record["Summary"] = extract_response_string(resp)
                        print(record)
                        outfile.write(json.dumps(record) + "\n")
                        success = True
                        break
                    except Exception as e:
                        local_retry -= 1
                        print("Summary generation failed:", e)
                        print("Retry: ", local_retry)

                if not success:
                    failed.append(record)

    print("All failed records: \n", failed)

### ----------------------------------------------------------------------------------------------------
### HTML and URL Parsing Functions
### ----------------------------------------------------------------------------------------------------

# function: looks_like_article
# uses a simple heuristic to guess if a url is an article
def looks_like_article(url):
    if "/2026/" in url or "/2025/" in url or "/2024/" in url:
        return True

    return url.count("/") > 4


# function: is_valid_article_url
# filters out links that are clearly not useful article pages
def is_valid_article_url(url):
    if not url or not url.strip():
        return False

    bad_patterns = [
        "mailto:",
        "twitter.com",
        "facebook.com",
        "instagram.com",
        "linkedin.com",
        "soundcloud.com",
        "zoom.us",
        "bsky.app",
        "/author/",
        "/topic/",
        "/tag/",
        "/category/",
        "/about",
        "/contact",
        "/donate",
        "/subscribe",
        "/privacy",
        "/feed",
        "/search",
        "/podcast",
        "/video",
        "#respond",
        "?output=amp",
    ]

    lowered = url.lower()
    for p in bad_patterns:
        if p in lowered:
            return False

    return True


# function: extract_html_links
# pulls and cleans links from a page using the page url as root
def extract_html_links(html_text, root_str):
    soup = BeautifulSoup(html_text, "html.parser")

    excluded_exts = (
        ".js", ".css", ".svg", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".xml"
    )
    blocked_paths = ["wp-content", "wp-includes", "assets", "static", "/js/", "/css/"]

    urls = []
    for tag in soup.find_all("a"):
        href = tag.get("href")
        if not href:
            continue

        full_url = urljoin(root_str, href).strip()
        parsed = urlparse(full_url)
        path = parsed.path.lower()
        lowered = full_url.lower()

        if parsed.scheme not in {"http", "https"}:
            continue
        if not path:
            continue
        if any(blocked in path for blocked in blocked_paths):
            continue
        if path.endswith(excluded_exts):
            continue
        if not parsed.netloc:
            continue
        if lowered.endswith("/") and path.count("/") <= 1:
            pass

        urls.append(full_url)

    return [u for u in urls if u.strip()]


# function: extract_html_content
# pulls text from headings and paragraphs and trims very long pages
def extract_html_content(html_text):
    res = ""
    soup = BeautifulSoup(html_text, "html.parser")

    for tag in soup.find_all(["h1", "h2", "h3", "p"]):
        text = tag.get_text(" ", strip=True)
        if text:
            res += text + "\n"
        if len(res) >= max_content_chars:
            break

    return res[:max_content_chars]


# function: get_urls_list
# turns a list of urls into a numbered string for ivy
def get_urls_list(url_list):
    url_list = [u for u in list(dict.fromkeys(url_list)) if u and u.strip()]
    res = ""
    idx = 1

    for u in url_list:
        res += f"{idx}. {u}\n"
        idx += 1

    return url_list, res


# function: html_chunk
# splits very long html into chunks if needed
def html_chunk(html_text, chunk_size=180000):
    start = 0
    resp = []

    if chunk_size >= len(html_text):
        resp.append(html_text)
        return resp

    while start != len(html_text):
        print("Start: ", start)
        idx = html_text.find(">", start + chunk_size) + 1
        resp.append(html_text[start:idx])
        start = idx
        if start == len(html_text) or start == 0:
            break

    return resp

### ----------------------------------------------------------------------------------------------------
### Crawl Decision Functions
### ----------------------------------------------------------------------------------------------------

# function: choose_vetted_urls
# asks ivy which links look like articles and falls back to heuristics if needed
def choose_vetted_urls(html_links, links, url, retry=2):
    if not html_links:
        return []

    valid = False
    local_retry = retry
    url_ledger = None

    while local_retry > 0:
        compile_url_prompt = f"""Here is a numbered list of urls found on a news webpage:\n{links}
For each link determine whether it is True or False if the link looks like it would lead to a news article.
Respond in this format only: {{<number>:<True or False>, <number>:<True or False>, ..., <number>:<True or False>}}"""

        print("LINKS BEING SENT TO IVY:")
        print(links)

        resp = prompt_ivy(compile_url_prompt, ivy_url_classify_system)
        print("RAW IVY RESPONSE:", repr(resp))
        print("RAW IVY RESULT:", repr(extract_response_string(resp)))
        resp_str = extract_response_string(resp).strip()

        if len(resp_str) == 0:
            local_retry -= 1
            print("Length of response was 0")
            continue

        log_ivy(resp)
        url_ledger = extract_dict_from_response(resp_str)

        if url_ledger is not None:
            print("URL EXTRACTION from: ", url)
            valid = True
            break

        print("UGHHHHHHH!!!!!!!!!!! Not in dictionary format")
        local_retry -= 1

    if valid and url_ledger is not None:
        vetted_url = []
        for i in range(len(html_links)):
            if url_ledger.get(i + 1, False):
                vetted_url.append(html_links[i])
        return vetted_url

    print("Falling back to heuristic article selection for:", url)
    return [u for u in html_links if looks_like_article(u)][:6]

### ----------------------------------------------------------------------------------------------------
### Core Crawl Functions
### ----------------------------------------------------------------------------------------------------

# function: site_crawl
# crawls one page, optionally follows child links, and stores summaries
def site_crawl(depth, url, usr, results, mode, retry=2, visited=None):
    if visited is None:
        visited = set()

    if not url or not url.strip():
        return

    if url in visited:
        print("Skipping already visited URL:", url)
        return
    visited.add(url)

    page = safe_get(url)
    if page is None:
        return

    html_content = extract_html_content(page.text)
    if not html_content.strip():
        print("Skipping page with empty extracted content:", url)
        return

    html_links = extract_html_links(page.text, page.url)
    html_links = [u for u in html_links if is_valid_article_url(u)]

    article_links = [u for u in html_links if looks_like_article(u)]
    other_links = [u for u in html_links if u not in article_links]
    html_links = (article_links + other_links)[:max_links_per_page]
    html_links, links = get_urls_list(html_links)

    print("html text len: ", len(html_content))

    if depth != 0 and html_links:
        vetted_url = choose_vetted_urls(html_links, links, url, retry=retry)
        for vu in vetted_url:
            print("Investigating URL: ", vu)
            site_crawl(depth - 1, vu, usr, results, mode, retry=retry, visited=visited)

    if mode == SUMMARIZE:
        ivy_prompt = (
            f"HTML:{html_content} UserInput: Summarize the content of this webpage in 4 sentences. "
            "Mention the main topic, key words and any social groups of people it mentions."
        )
    else:
        ivy_prompt = (
            f"HTML:{html_content} UserInput:{usr}\n"
            "If there is no relevant information to the UserInput reply only with the word None."
        )

    resp = prompt_ivy(ivy_prompt, ivy_html_system)

    print(f"URL: {url}")
    log_ivy(resp)

    record = {
        "Timestamp": crawl_time,
        "Depth": depth,
        "URL": page.url,
        "Summary": extract_response_string(resp)
    }
    results.append(record)
    print("Results length: ", len(results))


# function: search_web
# runs the full ivy flow to find relevant local news for a user query
def search_web(usr, state, community):
    discern_query = f"The user said this: {usr}\nwould a response to the above benefit from information from local news coverage?"

    discern_retry = 2
    while discern_retry != 0:
        resp = prompt_ivy(discern_query, ivy_discern_system)
        response_parts = extract_response_string(resp).split("|")
        log_ivy(resp)

        if len(response_parts) != 2:
            discern_retry -= 1
            continue
        elif response_parts[0].strip() == "Yes":
            print("Local news was deemed useful")
            break
        elif response_parts[0].strip() == "No":
            print("No internet search was deemed necessary")
            return []
        else:
            discern_retry -= 1
            continue

    if discern_retry == 0:
        print("Discernment failed")
        return []

    state_file = f"{news_region_resources}/{state}.jsonl"
    outlet_records = get_all_crawl_data(state_file, community)

    all_outlet_res = []
    for outlet_rec in outlet_records:
        root_name = outlet_rec["Outlet"]
        root = get_root(root_name)
        print("Root: ", root)

        global crawl_time
        crawl_time = datetime.datetime.now().strftime(timestamp_format)
        news_records = []

        print("Outlet has been selected as relevant: ", root_name)
        if redo_crawl_check(root, crawl_time):
            print("We are gonna crawl: ", root_name)
            visited_urls = set()
            site_crawl(crawl_depth, outlet_rec["Website"], usr, news_records, SUMMARIZE, visited=visited_urls)

            print("Final records length: ", len(news_records))
            print(f" Records: {news_records}")

            with open(get_outlet_cache_path(root_name), "w", encoding="utf-8") as crawl_file:
                for r in news_records:
                    crawl_file.write(json.dumps(r) + "\n")
        else:
            print("This site already has crawled relevant data stored: ", root_name)
            state_file = get_outlet_cache_path(root_name)
            news_records = get_all_crawl_data(state_file)

        filename = get_outlet_cache_path(root_name)
        summaries_text = get_summaries_list(filename)
        if summaries_text == "":
            print("Something went wrong with making the summary")
            continue

        eval_summaries_prompt = f"""Here is a numbered list of a summary of resources:\n{summaries_text}
For each summary determine whether it is True or False that a webpage with that content would be beneficial to providing a response to this user input: {usr}.
Respond in this format only: {{<number>:<True or False>, <number>:<True or False>, ..., <number>:<True or False>}}"""

        retry = 2
        valid = False
        record_ledger = {}

        while retry > 0:
            resp = prompt_ivy(eval_summaries_prompt, ivy_url_classify_system)
            log_ivy(resp)
            resp_str = extract_response_string(resp).strip()

            record_ledger = extract_dict_from_response(resp_str)
            if record_ledger is None:
                retry -= 1
                continue

            valid = True
            break

        if not valid:
            print("There was a problem getting the ledger")
            continue

        for i in range(len(news_records)):
            try:
                if record_ledger.get(i + 1, False):
                    print("Exploring record: ", i + 1)
                    target = news_records[i]
                    local_search_results = []
                    site_crawl(0, target["URL"], usr, local_search_results, SEARCH, visited=set())

                    if local_search_results and local_search_results[-1]["Summary"] != "None":
                        web_record = {
                            "Timestamp": local_search_results[-1]["Timestamp"],
                            "Outlet": root_name,
                            "URL": target["URL"],
                            "Info": local_search_results[-1]["Summary"]
                        }
                        all_outlet_res.append(web_record)
            except Exception as e:
                print("Error while exploring record", i + 1, ":", e)
                continue

        print("FINISHED PROCESSING: ", root_name)

    print("USER RELATED RESPONSE")
    for i, rec in enumerate(all_outlet_res):
        print(f"************ Response {i} ************")
        print(rec)
        print("************************\n")

    return all_outlet_res

### ----------------------------------------------------------------------------------------------------
### Logging Functions
### ----------------------------------------------------------------------------------------------------

# function: log_ivy
# prints ivy output when verbose mode is on
def log_ivy(response, verbose=verbose):
    phrase = f"Ivy: {extract_response_string(response)}\n"
    if verbose:
        print(phrase)