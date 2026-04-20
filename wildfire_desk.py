from build.lib.llmproxy import LLMProxy
import time
import datetime
import sys
from string import Template
from pathlib import Path

### ----------------------------------------------------------------------------------------------------
### System Settings      -
### ----------------------------------------------------------------------------------------------------

timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
verbose = True
display_rag = 0
chatbot_democracy_resources_directory = "sage-resources/democracy-chatbot-resources"
chatbot_wildfire_resources_directory = "sage-resources/wildfire-resources"
sage_instructions_directory = "sage-resources/sage-instructions"
upload_resources = False

### ----------------------------------------------------------------------------------------------------
### Sage Settings        -
### ----------------------------------------------------------------------------------------------------

sage = LLMProxy()
sage_tone = ""
sage_interaction = ""
sage_formatting = ""
sage_drafting = ""
sage_guardrails = ""
sage_intro = ""
sage_privacy = ""
sage_model = '4o-mini' # subject to change
sage_temperature = 0.6 # subject to change
sage_grounded_session_id = "sage_grounded_" + str(timestamp)
sage_general_session_id = "sage_general_" + str(timestamp)
sage_RAG_id = "sage_rag2"#+str(timestamp)
sage_rag_t = 0.4 # subject to change
sage_rag_k = 5 # top number of chunks to fetch to use for rag, lets see if we need to set this
sage_intro_session_id = "sage_intro_" + str(timestamp)
sage_lastk = 3

### ----------------------------------------------------------------------------------------------------
### Helpers        -
### ----------------------------------------------------------------------------------------------------

def load_text_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Error: could not find file {filepath}")
        return None
    except PermissionError:
        print(f"Error: permission denied when opening file {filepath}")
        return None
    except OSError as e:
        print(f"Error: could not open file {filepath}: {e}")
        return None


def build_sage_system_prompt():
    return "\n\n".join([
        sage_tone,
        sage_interaction,
        sage_formatting,
        sage_drafting,
        sage_guardrails,
        sage_privacy
    ])


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


def parse_retrieve_rag_context(rag_ctx):
    # the rag cotext from retrieve() is a list of dictionaries with the keys: doc_id, doc_summary and chunks.
    summaries = ""
    index = 1
    for rec in rag_ctx:
        summaries += f"""{str(index)}. {rec["doc_summary"]}\n"""
        index+=1
    
    return summaries, index


def get_sage_session_id(include_rag=True):
    if include_rag:
        return sage_grounded_session_id
    return sage_general_session_id

### ----------------------------------------------------------------------------------------------------
### Sage Setup        -
### ----------------------------------------------------------------------------------------------------

def upload_to_sage(filepath):
    response = sage.upload_file(
        file_path = filepath,
        session_id = sage_RAG_id,
        strategy = 'smart' 
    )
    time.sleep(3)
    if "result" not in response:
        print("Resource upload error\n")
        print("Full response:", response)
        return False
    resp_message = response["result"]
    if verbose and display_rag > 0:
        fileparts = str(filepath).split("/")
        name = fileparts[len(fileparts) - 1]
        print("Upload Status: " + resp_message + ", Filename: " + name)
    elif verbose:
        print("Upload Status: " + resp_message)
    return resp_message == "success"


def upload_2d_directory(filepath_str):
    p = Path(filepath_str)
    for data in p.iterdir():
        if data.is_dir():
            for file in data.iterdir():
                # print("Name: ", file.name, "Relative: ", file.relative_to("."), "\n")
                if not upload_to_sage(file.relative_to(".")):
                    print(f"""File: {file.name} - failed to upload\n""")
                    return False
        elif data.is_file():
            if not upload_to_sage(data.relative_to(".")):
                    print(f"""File: {data.name} - failed to upload\n""")
                    return False
    return True


def setup_sage():
    global sage_tone
    global sage_interaction
    global sage_formatting
    global sage_drafting
    global sage_guardrails
    global sage_intro
    global sage_privacy

    if upload_resources:
        if not upload_2d_directory(chatbot_democracy_resources_directory):
            return False
        if not upload_2d_directory(chatbot_wildfire_resources_directory):
            return False
    try:
        sage_tone = load_text_file(f"{sage_instructions_directory}/sage-tone.txt")
        sage_interaction = load_text_file(f"{sage_instructions_directory}/sage-interaction.txt")
        sage_formatting = load_text_file(f"{sage_instructions_directory}/sage-formatting.txt")
        sage_drafting = load_text_file(f"{sage_instructions_directory}/sage-drafting.txt")
        sage_guardrails = load_text_file(f"{sage_instructions_directory}/sage-guardrails.txt")
        sage_intro = load_text_file(f"{sage_instructions_directory}/sage-introduction.txt")
        sage_privacy = load_text_file(f"{sage_instructions_directory}/sage-privacy.txt")
    except:
        return False

    if (
        sage_tone is None or
        sage_interaction is None or
        sage_formatting is None or
        sage_drafting is None or
        sage_guardrails is None or
        sage_intro is None or
        sage_privacy is None
    ):
        print("One of more of sage's instructions failed to load.")
        return False

    return True

### ----------------------------------------------------------------------------------------------------
# Core Chat Logic
### ----------------------------------------------------------------------------------------------------

def prompt_sage(query_prompt, include_rag=True):
    final_query = ""
    rag_context = []

    if include_rag:
        rag_context = sage.retrieve(
            query=query_prompt,
            session_id=sage_RAG_id,
            rag_threshold=sage_rag_t,
            rag_k=sage_rag_k
        )

        final_query = Template("$query\n$rag_context").substitute(
            query=query_prompt,
            rag_context=rag_context_string_simple(rag_context)
        )
    else:
        final_query = query_prompt

    full_system_prompt = build_sage_system_prompt()
    active_session_id = get_sage_session_id(include_rag=include_rag)

    response = sage.generate(
        model=sage_model,
        system=full_system_prompt,
        query=final_query,
        temperature=sage_temperature,
        session_id=active_session_id,
        lastk=sage_lastk,
    )

    return response, rag_context


def get_intro():
    full_system_prompt = build_sage_system_prompt()

    response = sage.generate(
        model=sage_model,
        system=full_system_prompt,
        query=sage_intro,
        temperature=sage_temperature,
        session_id=sage_intro_session_id,
        lastk=0,
    )

    return response["result"]

def get_source(rag_context):
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
    
    # response, _ = prompt_sage(source_prompt) # Commented out and seems to be fixing the double citation problem, but tbh who knows

    doc_summaries = parse_retrieve_rag_context(rag_context)

    citation_prompt = f"""
        You are generating a short "Where this advice comes from" section for a user.

        Documents:
        {doc_summaries}

        Write the output in TWO parts:

        PART 1 — SUMMARY PARAGRAPH
        Write a short paragraph (2–3 sentences total) that:
        - explains what kinds of sources this advice draws from
        - describes the perspective or approach these sources take
        - clearly connects that perspective to the advice given

        Rules for the paragraph:
        - Use plain, non-academic language
        - Do not use markdown of any kind
        - Do not use bold, italics, or symbols such as ** or *
        - Do not use headings
        - Write in clean plain text only

        PART 2 — CITATIONS
        Under the paragraph, provide MLA-style citations for the same sources.

        Rules for citations:
        - Use a simple numbered list (1., 2., 3.)
        - Each citation must be a single line of plain text
        - Include only information that is available (author, title, date, publisher, link)
        - Do not guess or fabricate missing information
        - Do not use placeholders such as "[No date available]"
        - Do not use markdown
        - Do not use bold, italics, or symbols such as ** or *
        - Do not use headings
        - Do not include extra explanation

        FINAL OUTPUT RULES:
        - Return only plain text
        - Do not include section titles or labels
        - Do not include "MLA-style citations" or any header
        - Do not include markdown anywhere in the output
        """
    
    response, _ = prompt_sage(citation_prompt)
    return response["result"]
    
def chat_with_sage(user_message, mode="grounded"):
    use_rag = (mode == "grounded")

    response, rag_context = prompt_sage(user_message, include_rag=use_rag)
    answer = response["result"]

    sources = None
    if use_rag and len(rag_context) > 0:
        sources = get_source(rag_context)
    else:
        warning = (
            "Note: This answer is based on general knowledge and may not reflect "
            "specific local policies or up-to-date recovery information. "
            "You may want to verify details with local agencies."
        )
        answer = f"{answer}\n\n---\n{warning}"

    return {
        "answer": answer,
        "sources": sources,
        "used_rag": use_rag and len(rag_context) > 0,
        "rag_context": rag_context,
        "mode": mode
    }

### ----------------------------------------------------------------------------------------------------
### Logging Functions, Assess Question         -
### ----------------------------------------------------------------------------------------------------

def log_user(file, text, verbose=verbose):
    phrase = "Anon: " + text + "\n\n"
    file.write(phrase)
    
    if(verbose):
        print(phrase)

def log_sage(file, response, rag_context, verbose=verbose, display_rag=display_rag):
    phrase = ""
    
    if isinstance(response, dict):
        phrase = f"""Sage: {response.get("result")}\n"""
    elif isinstance(response, tuple):
        phrase = f"""Sage: {response[0]["result"]}\n"""
    else:
        phrase = f"""Sage: {response}\n"""
    
    file.write(phrase)
    
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


### ----------------------------------------------------------------------------------------------------
# Command Line Interface
### ----------------------------------------------------------------------------------------------------

def run_cli():
    if not setup_sage():
        print("An error occurred when setting up this application.")
        sys.exit(1)

    with open(f"log-{timestamp}.txt", "w", encoding="utf-8") as file:
        # Intro
        intro = get_intro()
        log_sage(file, intro, "")

        usr = input("Type your response here: ")

        while usr != "quit":
            # Log user input
            log_user(file, usr)

            # Core chat call
            result = chat_with_sage(usr, mode="grounded")

            # Log and print answer
            log_sage(file, result["answer"], result["rag_context"])

            # Show sources if they exist
            if result["sources"]:
                print("\nCitation Summary:\n")
                log_sage(file, result["sources"], "")
            else:
                print("WARNING: No vetted resources were used to produce the information above")

            # Next input
            usr = input("Type your response here: ")


if __name__ == '__main__':
    run_cli()