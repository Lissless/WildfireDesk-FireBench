from build.lib.llmproxy import LLMProxy
import time
import datetime
import sys
# I advocate for the name Sage for this bot
#   - its a plant that grows in dry areas such as California which is a huge target for wildfires
#   - its a name associated with wisdom and protection

### ----------------------
### System Settings      -
### ----------------------

timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
verbose = True
display_rag = 1

### ----------------------
### Sage Settings        -
### ----------------------

sage = LLMProxy()
sage_core = "" # to be uploaded upon setup
sage_model = '4o-mini' # subject to change
sage_temperature = 0.6 # subject to change
sage_session_id = "sage"+str(timestamp) # subject to change --> may need to save
sage_rag_t = 0.2 # subject to change
sage_rag_k = 10 # top number of chunks to fetch to use for rag, lets see if we need to set this

example_rag = ""

def upload_to_sage(filepath):
    response = sage.upload_file(
        file_path = filepath,
        session_id = sage_session_id,
        strategy = 'smart' 
    )
    time.sleep(2)
    if "result" not in response:
        print("Resource upload error\n")
        return False
    resp_message = response["result"]
    print("Upload Status: " + resp_message + "\n")
    return resp_message == "success"

def prompt_sage(query_prompt):
    response = sage.generate(
        model = sage_model,
        system = sage_core,
        query = query_prompt,
        temperature = sage_temperature,
        session_id = sage_session_id,
        rag_usage = True, # I cannot see a world where this is not True
        rag_threshold=sage_rag_t,
        rag_k=sage_rag_k
    )

    context = sage.retrieve(
        query = query_prompt,
        session_id = sage_session_id,
        rag_threshold=sage_rag_t,
        rag_k=sage_rag_k
    )

    print(f"""\n!!!!!!!!!!!!!!!!!!!!!!!\nretrieved: {context}\n!!!!!!!!!!!!!!!!!!!!!!!\n""")

    return response

# returns if this was successful or not
def setup_sage():
    # upload and store the string contents of the tone 
    if not upload_to_sage("sage-resources/question-types.pdf"):
        return False
    if not upload_to_sage("sage-resources/democracy-chatbot-resources/strategy-and-organizing/198 Methods of Nonviolent Action — AEI_ Empowering Humankind.pdf"):
        return False
    if not upload_to_sage("sage-resources/democracy-chatbot-resources/strategy-and-organizing/Ella Taught Me: Shattering the Myth of the Leaderless Movement - Colorlines.pdf"):
        return False
    if not upload_to_sage("sage-resources/democracy-chatbot-resources/strategy-and-organizing/Leading with Network Mindset .pdf"):
        return False
    try:
        with open("sage-resources/sage-tone.txt") as f:
            global sage_core
            sage_core = f.read()
    except:
        return False
    return True

### ----------------------
### Soil Settings        -
### ----------------------

sage = LLMProxy()
sage_core = "" # to be uploaded upon setup
sage_model = '4o-mini' # subject to change
sage_temperature = 0.6 # subject to change
sage_session_id = "sage"+str(timestamp) # subject to change --> may need to save
sage_rag_t = 0.4 # subject to change
sage_rag_k = 5 # top number of documents to fetch to use for rag, lets see if we need to set this


### -----------------------
### Static Prompts        -
### -----------------------

introduction_prompt = "Introduce yourself and say what it is you can do for the user. Mention to call authorities if this is an urgent emergency."

### -----------------------
### Main Prompts         -
### -----------------------

def get_source(file, rag_context):
    source_prompt = f"""What documents are referenced in this Rag Context?<start> {rag_context} <end>
    
    If there is only empty space between <start> and <end> reply with three empty spaces.

    Otherwise, make sure your answer follows the format: **[Document Name]**\n - [Summary]\n - [Key sections referenced]
    """
    # Here is an example of that format:
    # 1. **"Ella Taught Me: Shattering the Myth of the Leaderless Movement" - Colorlines**
    # - This document addresses the misconception of leaderless movements, emphasizing the importance of organized leadership and collective strategy within social movements. It references historical examples such as the Student Nonviolent Coordinating Committee (SNCC) and the Black Panther Party, highlighting the concept of group-centered leadership as essential for accountability and effective mobilization.
    # - Key Sections:
    #     - **Group-Centered Leadership**: Discusses the necessity for structured organizations like the Black Youth Project 100 (BYP100) and their approach to activism.
    #     - **Collective Strategy**: Emphasizes the need for organizations to ensure accountability and coordinated efforts among activists.
    #     - **Experiences in Movements**: Reflects on the author's experiences balancing mobilization with organization-building and the importance of communication.
    

    response = prompt_sage(source_prompt)
    log_sage(file, response)

    citation_prompt = f"""Here is some information on documents Sage referenced: <start> {response["result"]}<end>\n  
    If there is only empty space between <start> and <end> then respond by saying 'No resources were referenced to make the above response'.
    Otherwise, give a citation for each resource mentioned between <start> and <end>. 
    Respond with only citations in MLA format, if you are not able to fill in a portion of the citation then omit it. Do not write duplicate citations. Do not use citations from the reference portion of the document, only cite the document itself."""
    response = prompt_sage(citation_prompt)
    # log_sage(file, response)
    return response
    
def log_user(file, text, verbose=verbose):
    phrase = "Anon: " + text + "\n\n"
    file.write(phrase)
    if(verbose):
        print(phrase)

def log_sage(file, response, verbose=verbose, display_rag=display_rag):
    phrase = "Sage: " + response["result"] + "\n"
    file.write(phrase)
    if(verbose):
        print(phrase)
    if(display_rag == 1):
        print(f"""\n******************\nRag_context: {response["rag_context"]} \nRag_context_length: {len(response["rag_context"])} \n******************\n\n""")
    elif(display_rag == 2):
        print(f"""\n******************\nRag_context_length: {len(response["rag_context"])} \n******************\n\n""")


def assess_question_type(file, text):
    assess_prompt = f"""The user has asked this: {text}\n\n Based on question-types.pdf, what category does this question fall into? 
    If it is not a question say its category is Non-Question. Give your reasoning for your choice. The final answer should follow a newline character."""
    resp = prompt_sage(assess_prompt)
    log_sage(file, resp, verbose)

def main():
    if not setup_sage():
        print("An error occured when setting up this application, please refresh or return at a later time.")
        sys.exit(1)
    #log collection with debugging
    with open(f"""log-{timestamp}.txt""", "w", encoding="utf-8") as file:
        resp = prompt_sage(introduction_prompt)
        log_sage(file, resp)
        usr = input("Type your response here: ")
        # log_user(file, usr)
        with open("sage-resources/example-rag.txt") as f:
            global example_rag
            example_rag = f.read()
        while usr != "quit":
            resp = prompt_sage(usr)
            log_sage(file, resp)
            citations = get_source(file, resp["rag_context"])
            log_sage(file, citations)

            # get_source(file, example_rag)
            usr = input("Type your response here: ")
            log_user(file, usr)

if __name__ == '__main__':
    main()


# Example tester questions for citations
# What is action 109 of nonviolent actions
# How could i lead a leaderless movement and tell me how that would relate to nonviolent action 106
# In reference to nonviolent action 106, how would I run a leaderless movement to acomplish that non-violent action
# In reference to nonviolent action 106, how would I run a leaderless movement to acomplish that non-violent action and how would I develop my network in this highly connected world?
# why do network strateigies deserve our attention?
# how would a leaderless movement do 198 methods of nonviolent action?


# Doc ids
# 9eac9c1d32fca5fc8439a79f97582ede56b4931095bd98f37bc99f00705fe2f7
# a3fb96284ccdf694077f279689b85c650e21f79256f61acd560c1fd5c61fa41b
# a3fb96284ccdf694077f279689b85c650e21f79256f61acd560c1fd5c61fa41b
# 9a78d8df722135e34daaa5ea9912e42dbd5b5a0565ff845282001d75df58b64c
# 9a78d8df722135e34daaa5ea9912e42dbd5b5a0565ff845282001d75df58b64c
# 9a78d8df722135e34daaa5ea9912e42dbd5b5a0565ff845282001d75df58b64c
# 9a78d8df722135e34daaa5ea9912e42dbd5b5a0565ff845282001d75df58b64c
