from build.lib.llmproxy import LLMProxy
import time
import datetime
import sys
from string import Template
# I advocate for the name Sage for this bot
#   - its a plant that grows in dry areas such as California which is a huge target for wildfires
#   - its a name associated with wisdom and protection

### ----------------------
### System Settings      -
### ----------------------

timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
verbose = True
display_rag = 1

def rag_context_string_simple(rag_context):

    """
    Convert the RAG context list (from retrieve API)
    into a single plain-text string that can be appended to a query.
    """

    context_string = ""

    i=1
    for collection in rag_context:
    
        if not context_string:
            context_string = """The following is additional context that may be helpful in answering the user's query."""

        context_string += """
        #{} {}
        """.format(i, collection['doc_summary'])
        j=1
        for chunk in collection['chunks']:
            context_string+= """
            #{}.{} {}
            """.format(i,j, chunk)
            j+=1
        i+=1
    return context_string

### ----------------------
### Sage Settings        -
### ----------------------

sage = LLMProxy()
sage_core = "" # to be uploaded upon setup
sage_model = '4o-mini' # subject to change
sage_temperature = 0.6 # subject to change
sage_session_id = "sage"+str(timestamp) # subject to change --> may need to save
sage_RAG_id = "sage_rag"+str(timestamp)
sage_rag_t = 0.2 # subject to change
sage_rag_k = 10 # top number of chunks to fetch to use for rag, lets see if we need to set this

example_rag = ""

def upload_to_sage(filepath):
    response = sage.upload_file(
        file_path = filepath,
        session_id = sage_RAG_id,
        strategy = 'smart' 
    )
    time.sleep(2)
    if "result" not in response:
        print("Resource upload error\n")
        return False
    resp_message = response["result"]
    print("Upload Status: " + resp_message + "\n")
    return resp_message == "success"

def prompt_sage(query_prompt, include_rag=True):
    final_query = ""
    if include_rag:
        rag_context = sage.retrieve(
            query = query_prompt,
            session_id = sage_RAG_id,
            rag_threshold=sage_rag_t,
            rag_k=sage_rag_k
        )

        final_query = Template("$query\n$rag_context").substitute(
                                query=query_prompt,
                                rag_context=rag_context_string_simple(rag_context))
    else:
        final_query = query_prompt

    response = sage.generate(
        model = sage_model,
        system = sage_core,
        query = final_query,
        temperature = sage_temperature,
        session_id = sage_session_id,
        lastk=3, # the citation proccess usually take three prompts, unsure if this is helpful
    )
    #     rag_usage = True, # I cannot see a world where this is not True
    #     rag_threshold=sage_rag_t,
    #     rag_k=sage_rag_k
    # )

    

    # print(f"""\n!!!!!!!!!!!!!!!!!!!!!!!\nretrieved: {rag_context}\n!!!!!!!!!!!!!!!!!!!!!!!\n""")

    return response, rag_context

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
    # Here is an example of that format:
    # 1. **"Ella Taught Me: Shattering the Myth of the Leaderless Movement" - Colorlines**
    # - This document addresses the misconception of leaderless movements, emphasizing the importance of organized leadership and collective strategy within social movements. It references historical examples such as the Student Nonviolent Coordinating Committee (SNCC) and the Black Panther Party, highlighting the concept of group-centered leadership as essential for accountability and effective mobilization.
    # - Key Sections:
    #     - **Group-Centered Leadership**: Discusses the necessity for structured organizations like the Black Youth Project 100 (BYP100) and their approach to activism.
    #     - **Collective Strategy**: Emphasizes the need for organizations to ensure accountability and coordinated efforts among activists.
    #     - **Experiences in Movements**: Reflects on the author's experiences balancing mobilization with organization-building and the importance of communication.
    source_prompt = f"""What documents are referenced in the doc_summary sections of this Rag Context?<start> {rag_context} <end>
    
    If there is only empty space between <start> and <end> reply with three empty spaces.

    Otherwise, make sure your answer follows the format: **[Document Name]**\n - [Summary]\n - [Key sections referenced]
    """
    
    response, _ = prompt_sage(source_prompt)
    # log_sage(file, response, "irrelevant 1")

    # doc_data = ""
    # if isinstance(response, dict):
    #     doc_data = response["result"]
    # elif isinstance(response, tuple):
    #     doc_data = response[0]["result"]
    # else:
    #     doc_data = response

    # print(f"""\nDoc data: {doc_data}\n""")

    doc_summaries, number = parse_retrieve_rag_context(rag_context)
    # print(f"""Doc Summaires: {doc_summaries}\n""")

    # citation_prompt = f"""Here are the summaries of each document Sage referened in the previous prompt: <start> {doc_summaries}<end>\n  
    # If there is only empty space between <start> and <end> then respond by saying 'No resources were referenced to make the above response'.
    # Otherwise, If there is information it is in the format **[Document Name]**\n - [Summary]\n - [Key sections referenced]
    # Give a citation for each document mentioned between <start> and <end>. 
    # Respond only with citations in MAL format. If you are not able to fill in a portion of the citation then omit it. Do not write duplicate citations. Do not use citations from the reference portion of the document, only cite the document itself."""

    citation_prompt = f""" Give MLA format citations for each document referenced below:\n {doc_summaries}\n 
    If you are not able to fill in a portion of the citation then omit it. Only return the top {number} relevant citation(s)."""
    # There should be one citation per document referenced.
    # citation_prompt = f"""Here is some information on documents Sage referenced: <start> {doc_data}<end>\n  
    # If there is only empty space between <start> and <end> then respond by saying 'No resources were referenced to make the above response'.
    # Otherwise, If there is information it is in the format **[Document Name]**\n - [Summary]\n - [Key sections referenced]
    # Give a citation for each document mentioned between <start> and <end>. 
    # Respond only with citations in MAL format. If you are not able to fill in a portion of the citation then omit it. Do not write duplicate citations. Do not use citations from the reference portion of the document, only cite the document itself."""
    response, ctx = prompt_sage(citation_prompt)
    # log_sage(file, response)
    return response, ctx
    
def parse_retrieve_rag_context(rag_ctx):
    # the rag cotext from retrieve() is a list of dictionaries with the keys: doc_id, doc_summary and chunks.
    summaries = ""
    index = 1
    for rec in rag_ctx:
        summaries += f"""{str(index)}. {rec["doc_summary"]}\n"""
        index+=1
    
    return summaries, index

def log_user(file, text, verbose=verbose):
    phrase = "Anon: " + text + "\n\n"
    file.write(phrase)
    if(verbose):
        print(phrase)

def log_sage(file, response, rag_context, verbose=verbose, display_rag=display_rag):
    phrase = ""
    print(f"""Type: {type(response)}\n""")
    if isinstance(response, dict):
        phrase = f"""Sage: {response.get("result")}\n"""
    elif isinstance(response, tuple):
        phrase = f"""Sage: {response[0]["result"]}\n"""
    else:
        print("The Else")
        phrase = f"""Sage: {response}\n"""
    # phrase = "Sage: " + response["result"] + "\n"
    file.write(phrase)
    # if(verbose):
    #     print(phrase)
    # if(display_rag == 1):
    #     print(f"""\n******************\nRag_context: {response["rag_context"]} \nRag_context_length: {len(response["rag_context"])} \n******************\n\n""")
    # elif(display_rag == 2):
    #     print(f"""\n******************\nRag_context_length: {len(response["rag_context"])} \n******************\n\n""")

    if(verbose):
        print(phrase)
    if(display_rag == 1):
        print(f"""\n******************\nRag_context: {rag_context} \nRag_context_length: {len(rag_context)} \n******************\n\n""")
    elif(display_rag == 2):
        print(f"""\n******************\nRag_context_length: {len(rag_context)} \n******************\n\n""")


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
        log_sage(file, resp, "")
        usr = input("Type your response here: ")
        # log_user(file, usr)
        with open("sage-resources/example-rag.txt") as f:
            global example_rag
            example_rag = f.read()
        while usr != "quit":
            resp, rag_context = prompt_sage(usr)
            log_sage(file, resp, rag_context)
            if len(rag_context) > 0:
                citations, rag_context = get_source(file, rag_context)
                log_sage(file, citations, rag_context)

            # get_source(file, example_rag)
            usr = input("Type your response here: ")
            log_user(file, usr)

if __name__ == '__main__':
    main()


# Example tester questions for citations
# why do network strateigies deserve our attention?
# how would a leaderless movement do 198 methods of nonviolent action?
# what is the nonviolent method number 31?
