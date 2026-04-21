from build.lib.llmproxy import LLMProxy
import datetime
from os import walk
import requests
import json
import ast
from bs4 import BeautifulSoup
from urllib.parse import urlparse

### ----------------------------------------------------------------------------------------------------
### System Settings      -
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

# I want to make a social group that tartet problemt black voters care about, what shoudl I put in my mission statement to be relevant?

### ----------------------------------------------------------------------------------------------------
### Ivy Settings        -
### ----------------------------------------------------------------------------------------------------
# I propose our web crawler be named Ivy! This is a crawling and climbing vine that (unfortunately) can spread
# fires, especially in california


ivy = LLMProxy()
ivy_model = 'gemini-2.5-flash-lite'
# ivy_html_system = f"""You will receive the raw HTML of a webpage. Extract the key findings, important topics, and any key dates. Respond briefly and clearly."""
ivy_html_system = f"""You will receive the raw HTML of a webpage and user input in the format HTML:<HTML> UserInput:<usr>. Extract the key findings from the webpage that is related to the user input. Respond briefly and clearly."""
# ivy_discern_system = f"""You will receive a question, first answer with either 'Yes' or 'No'. Then respond with a reason in the format: Why: <reason>."""
ivy_discern_system = f"""respond in the format: <Yes or No>|<reason why>"""
ivy_url_disection = f"""You will recieve a list of links from a webpage and a user input in the format URLs:<URL list> UserInput:<usr>. Return all urls that would lead to a news article in the format: [<url>, <url>, ... <url>]. For example: [\"https://foo\", \"https://bar\"]. If there are no urls present respond with: []"""
ivy_session_id = "ivy"+str(timestamp)
ivy_temperature = 0.2 # subject to change

def add_summary(state, move_ahead=0):
    input_file = f"""sage-resources/state-local-news-outlets/{state}.jsonl"""
    output_file = f"""sage-resources/state-local-news-summaries/{state}.jsonl"""
    retry = 2
    failed = []

    with open(input_file, "r", encoding="utf-8") as infile, \
     open(output_file, "a", encoding="utf-8") as outfile:
        skip = 0


        for line in infile:
            if skip != move_ahead:
                skip += 1
                print("Skip: ", skip)
                continue
            record = json.loads(line)
            url = record["Website"]
            local_retry = retry
            success = False
            if "http" in url:
                while local_retry != 0:
                    try:
                        page = requests.get(url)
                        # Add summary field
                        html_content = extract_html_content(page.text)
                        # ivy_prompt = f"""HTML:{html_content} UserInput: Summarize the content of this webpage in 4 sentences. Mention the main topic, key words and any social groups of people it mentions. Then determine if it is True or False that you were able to make a meaningful summary of the webpage.
                        # Return your response in the format: <Summary>|<True or False>"""

                        ivy_prompt = f"""HTML:{html_content} UserInput: Summarize the content of this webpage in 4 sentences. Mention the main topic, key words and any social groups of people it mentions."""

                        resp = prompt_ivy(ivy_prompt, ivy_html_system)
                        record["Summary"] = extract_response_string(resp)

                        print(record)
                        # Write updated record
                        outfile.write(json.dumps(record) + "\n")
                        success = True
                        break
                    except:
                        # just give up on this one and continue
                        local_retry -= 1
                        print("Retry: ", local_retry)
                if not success:
                    failed.append(record)
    
    print("All failed records: \n", failed)

def get_all_supported_states():
    states = []
    # _, _, state_files = 
    for (_, _, filenames) in walk(news_region_resources):
        for file in filenames:
            fname = file.replace("_", " ")
            state_name = fname.split(".")[0]
            states.append(state_name)
        break
    return states

# The General community will encompass all new sites that have the community listed as - or --
def get_all_supported_communities(state):
    communitites = set()
    state_file = f"""{news_region_resources}/{state}.jsonl"""
    with open(state_file, "r", encoding="utf-8") as infile:
        for line in infile:
            record = json.loads(line)
            com = record["Community"]
            if com.count("-") != len(com):
                communitites.add(com)
            else:
                communitites.add("General")

    return list(communitites)

     
def search_web(usr, state, community):    
    discern_query = f"""The user said this: {usr}\nwould an response to the above benefit from information from local news coverage?"""

    discern_retry = 2
    while discern_retry != 0:
        resp = prompt_ivy(discern_query, ivy_discern_system)
        response_parts = extract_response_string(resp).split("|")
        log_ivy(resp)
        if len(response_parts) != 2:
            # Something has gone wrong with formatting, dont conduct internet search
            discern_retry -= 1
            continue
        elif response_parts[0] == "Yes":
            print("Local news was deemed useful")
            break
        elif response_parts[0] == "No":
            print("No internet search was deemed necessary")
            return []
        else:
            discern_retry -= 1
            continue
    if discern_retry == 0:
        print("Discernment failed")
        return []
    
    state_file = f"""{news_region_resources}/{state}.jsonl"""
    outlet_records = get_all_crawl_data(state_file, community)

    all_outlet_res = []
    for i in range(len(outlet_records)):
        outlet_rec = outlet_records[i]
        root_name = outlet_rec["Outlet"]
        root = get_root(root_name)
        print("Root: ", root)
        global crawl_time # TODO: re-eval whether or not this needds to be a global
        crawl_time = datetime.datetime.now().strftime(timestamp_format)
        news_records = []
        print("Outlet has been selected as relevant: ", root_name)
        if redo_crawl_check(root, crawl_time):
            print("We are gonna crawl: ", root_name)
            site_crawl(crawl_depth, outlet_rec["Website"], usr, news_records, SUMMARIZE)
            
            print("Final records length: ", len(news_records))
            print(f""" Records: {news_records}""")
            # Note below completely cleans the file any time its opened like this, if we want to keep
            # record we will need to implement extra logic
            crawl_file = open(f"""{news_resources}/{root_name}.jsonl""", "w")
            for r in news_records:
                crawl_file.write(json.dumps(r) + "\n")
            crawl_file.close()
        else:
            print("This site already has crawled relevant data stored: ", root_name)
            state_file = f"""{news_resources}/{root_name}.jsonl"""
            news_records = get_all_crawl_data(state_file)
        filename = f"""{news_resources}/{root_name}.jsonl"""
        sum = get_summaries_list(filename)
        if sum == "":
            print("Something went wrong with making the summary")
            return all_outlet_res
        eval_summaries_prompt = f"""Here is a numbered list of a summary of resources:\n{sum}
        For each summary determine whether it is True or False that a webpage with that content would be beneficial to providing a response to this user input: {usr}.
        Respond in this format: {{<number>:<True or False>, <number>:<True or False>, ..., <number>:<True or False>}}"""

        print(eval_summaries_prompt)

        retry = 2
        valid = False
        record_ledger = {}
        while retry > 0:
            resp = prompt_ivy(eval_summaries_prompt, ivy_html_system)
            log_ivy(resp)
            resp_str = extract_response_string(resp)
            try:
                record_ledger = ast.literal_eval(resp_str)
            except:
                retry -= 1
                continue
            valid = True
            break
        
        if not valid:
            print("There was a problem getting the ledger")
            return all_outlet_res

        # THis will aggregate the information based on what the usr asked and the content
        web_info = []
        for i in range(len(news_records)):
            try:
                if record_ledger[i + 1]:
                    print("Exploring record: ", i+1)
                    target = news_records[i]
                    site_crawl(0, target["URL"], usr, web_info, SEARCH)
                    if web_info[-1]["Summary"] != "None":
                        web_record = {
                            "Timestamp": web_info[-1]["Timestamp"],
                            "Outlet": root_name, # TODO: replace this with the non-underscored version
                            "URL": target["URL"],
                            "Info": web_info[-1]["Summary"]
                        }
                        all_outlet_res.append(web_record)
            except:
                # the enumeration would fall here because the website had no information of note and thus never got an entry
                continue
        print("FINISHED PROCESSING: ", root_name)

    print("USER RELATED RESPONSE")
    for i in range(len(all_outlet_res)):
        print(f"""************ Response {i} ************""")
        print(all_outlet_res[i])
        print("************************\n")

    return all_outlet_res

# There are two modes, summarize and search:
#               * SUMMARIZE gets the summary of the webpage
#               * SEARCH pulls information related to the usr statement
def site_crawl(depth, url, usr, results, mode, retry=2):
    page = requests.get(url)
    html_content = extract_html_content(page.text)
    html_links = extract_html_links(page.text, url)
    html_links, links = get_urls_list(html_links)
    print("html text len: ", len(html_content))

    if depth != 0:
        valid = False
        local_retry = retry 
        while local_retry > 0:
            compile_url_prompt = f"""Here is a numbered list of urls found on a news webpage:\n{links}. 
            For each link determine whether it is True or False if the link looks like it would lead to a news article.
            Respond in this format only: {{<number>:<True or False>, <number>:<True or False>, ..., <number>:<True or False>}}"""

            resp = prompt_ivy(compile_url_prompt, ivy_html_system)
            resp_str = extract_response_string(resp).strip()
            if len(resp_str) == 0:
                    local_retry -= 1
                    print("Length of response was 0")
                    continue
            log_ivy(resp)
            print(f"""resp_str[0]: {resp_str[0]}, resp_str[-1]: {resp_str[-1]}""")
            if resp_str[0] == "{" and resp_str[-1] == "}":
                # we have successfully got a dictionary format from Ivy
                print("URL EXTRACTION from: ", url)
                valid = True
                break
            else:
                print("UGHHHHHHH!!!!!!!!!!! Not in dictionary format")
            local_retry -= 1
        if not valid:
            #TODO: determine if something specific needs to be retruned in case of failure
            return
        
        vetted_url = []
        url_ledger = ast.literal_eval(resp_str)
        for i in range(len(html_links)):
            if url_ledger[i + 1]:
                vetted_url.append(html_links[i])

        for vu in vetted_url:
            print("Investigating URL: ", vu)
            site_crawl(depth - 1, vu, usr, results, mode, retry)
        
    # check if there is an existing record
    if mode == SUMMARIZE:
        ivy_prompt = f"""HTML:{html_content} UserInput: Summarize the content of this webpage in 4 sentences. Mention the main topic, key words and any social groups of people it mentions."""
    else:
        ivy_prompt = f"""HTML:{html_content} UserInput:{usr}\nIf there is no relevant information to the UserInput reply only with the word None. """

    resp = prompt_ivy(ivy_prompt, ivy_html_system)

    print(f"""URL: {url}""")
    log_ivy(resp)

    record = {
        "Timestamp": crawl_time,
        "Depth": depth,
        "URL": url,
        "Summary": extract_response_string(resp)
    }
    results.append(record)
    print("Results length: ", len(results))

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

# This function will tell us if we shole re-scrape the website if the 
def redo_crawl_check(record, current_time_str):
    if record == None:
        return True
    record_time = datetime.datetime.strptime(record["Timestamp"], timestamp_format)
    current_time = datetime.datetime.strptime(current_time_str, timestamp_format)
    diff = current_time - record_time
    return diff.days >= timestamp_stale_allowance

def extract_html_links(html_text, root_str):
    soup = BeautifulSoup(html_text, "html.parser")
    
    # Common attributes that contain URLs
    res = ""
    attrs = ["href"]
    excluded_exts = (".js", ".css", ".svg", ".jpg", ".png")

    blocked_paths = ["wp-content", "wp-includes", "assets", "static", "js", "css"]
    
    for tag in soup.find_all('a'):
        for attr in attrs:
            url = tag.get(attr) 
            parsed = urlparse(url)
            path = parsed.path.lower()
            if url and path:
                for b in blocked_paths:
                    if b in path:
                        cont = True
                        break
                if root_str[-1] == "/":
                    # shave off last character
                    root_str = root_str[:len(root_str)-1]
                if "http" not in url:
                    if url[0] != "/":
                        url = url + "/" + url
                    url = root_str + url
                if not path.endswith(excluded_exts):
                    res = res + url
                res = res + "|"
    
    res = res[:-2]
    res = res.split("|")
    return res

def extract_html_content(html_text):
    sections = []
    res = ""

    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup.find_all(["h1", "h2", "h3", "p"]):
        sections.append({
            "type": tag.name,
            "text": tag.get_text(strip=True)
        })
        res = res + tag.get_text(strip=True) + "\n"

    return res

def get_root(root_name):
    # This is funciton works two fold, it checks if the crawl file exists and it returns the record for the root of the file (homepage of the site)
    # The timestamp of all records should be the same so we just need to check that it is within the time allowed for stale data
    # IDEA: Articles are unlikely to change, but the homepage would feature new articles daily, we could keep old ones as a record and reference them later...
    try:
        name = f"""{news_resources}/{root_name}.jsonl"""
        print("getting root of nanma: ", name)
        crawl_file = open(f"""{news_resources}/{root_name}.jsonl""")
        root = json.loads(crawl_file.readline())
        print("get root root: ", root)
        crawl_file.close()
        return root
    except:
        # the record dosent exist, exit
        print("Failed get root open")
        return None

def get_crawl_record(url, root_name):
    # if a record is present returns that record if not returns None
    try:
        crawl_file = open(f"""{news_resources}/{root_name}.jsonl""")

        line = crawl_file.readline()
        # when line is none then that is the end of the file
        while line:
            record = json.loads(line)
            if record["URL"] == url:
                return record
            line = crawl_file.readline()
        crawl_file.close()
    except:
        # the record dosent exist, exit
        return None
    return None

def get_all_crawl_data(filename, community=None):
    res = []
    try :
        crawl_file = open(filename)
        line = crawl_file.readline()

        while line:
            record = json.loads(line)
            if community != None:
                if record["Community"].count("-") == len(record["Community"]):
                        print("General Conversion")
                        record["Community"] = "General"
                if record["Community"] != community:
                        print("Failed community check: ", record)
                        line = crawl_file.readline()
                        continue
            res.append(record)
            line = crawl_file.readline()
        crawl_file.close()
    except:
        print("get all crawl data bad exit")
        return res
    return res

#I am trying to make a social group that pertains to black voters, what things shoudl I include in the mission of my group?
# There are going to be two modes:
#       0. Makes the summaries of all records and returns all records
#       1. Makes summaries and logs records that are from a particular community
def get_summaries_list(filename):
    sum = ""
    idx = 1
    records = []
    try:
        crawl_file = open(filename)

        line = crawl_file.readline()
        # when line is none then that is the end of the file
        while line:
            record = json.loads(line)
            sum = sum + f"""{idx}. {record["Summary"]}\n"""
            records.append(record)
            line = crawl_file.readline()
            idx += 1
            print("Looking at record number: ", idx)
        crawl_file.close()
    except:
        # the record dosent exist, exit
        return sum
    return sum

def get_urls_list(url_list):
    url_list = list(set(url_list))
    res = ""
    idx = 1
    for u in url_list:
        res = res + f"""{idx}. {u}\n"""
        idx += 1
    return url_list, res

def prompt_ivy(query_prompt, ivy_sys):

    response = sage.generate(
        model = ivy_model,
        system = ivy_sys,
        query = query_prompt,
        temperature = ivy_temperature,
        session_id = ivy_session_id,
    )

    return response


### ----------------------------------------------------------------------------------------------------
### Logging Functions, Assess Question         -
### ----------------------------------------------------------------------------------------------------

def log_ivy(response, verbose=verbose):
    phrase = f"""Ivy: {extract_response_string(response)}\n"""    
    # file.write(phrase)

    if(verbose):
        print(phrase)

def extract_response_string(response):
    if isinstance(response, dict):
        res = response.get("result")
    elif isinstance(response, tuple):
        res = response[0]["result"]
    else:
        res = response
    
    return res