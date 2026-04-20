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
upload_resources = False

### ----------------------------------------------------------------------------------------------------
### Sage Settings        -
### ----------------------------------------------------------------------------------------------------

sage = LLMProxy()
sage_core = "" # to be uploaded upon setup
sage_model = '4o-mini' # subject to change
sage_temperature = 0.6 # subject to change
sage_session_id = "sage"+str(timestamp) # subject to change --> may need to save
sage_RAG_id = "sage_rag2"#+str(timestamp)
sage_rag_t = 0.4 # subject to change
sage_rag_k = 5 # top number of chunks to fetch to use for rag, lets see if we need to set this
sage_lastk = 10

### ----------------------------------------------------------------------------------------------------
### Static Prompts        -
### ----------------------------------------------------------------------------------------------------

introduction_prompt = """
Introduce yourself as Sage, a civic helpdesk assistant for wildfire recovery.

Structure the response in short paragraphs (2–3 sentences each), not one long block.

1. Start with a brief introduction of who you are and what you can help with (FEMA, insurance, housing, rebuilding, and next steps).

2. In a new paragraph, explain that you help users understand their options and figure out what actions to take. Mention that this can apply 
whether they are handling something individually or working with others. Also mention that you can help draft useful materials (such as emails, plans, or meeting agendas) when helpful.

3. In a new paragraph, ask 1–2 simple clarifying questions to understand their situation (what they are trying to do, and optionally whether they are acting alone or with others).

4. In a short, separate sentence, note that responses are anonymous and users should avoid sharing sensitive personal details unless necessary.

5. End with a separate sentence reminding them to contact emergency services (call 911) if they are in immediate danger.

Keep the tone professional, clear, and supportive. Avoid long sentences.
"""

formatting_prompt = """
Response Formatting

Write responses in a structured, easy-to-scan format for a web interface.

Choose the format that best fits the content. Vary your structure across responses:
- use numbered steps for processes
- use bullet points for recommendations or checklists
- use tables for comparisons, roles, timelines, or structured plans
- use simple labeled sections or arrows (→) to show flow or relationships

Do not rely on a single format. Adapt structure to make the answer clearer and more actionable. 
No need to repeat that responses are anonymous and to avoid sharing sensitive personal details. The user already knows that.

Guidelines:
- prioritize clarity and usability over verbosity
- prefer structured layouts over long paragraphs
- keep spacing and formatting clean and consistent

Avoid:
- markdown bold using ** **
- raw HTML
- long dense paragraphs
"""

drafting_prompt = """
Drafting Support

Whenever it would be genuinely helpful, proactively offer to draft a useful document or template for the user.

Examples include:
- meeting agendas
- outreach emails or letters
- checklists
- decision worksheets
- complaint drafts
- reflection or evaluation plans
- role descriptions
- follow-up messages

Only make this offer when it clearly fits the situation. Do not add a drafting offer to every response by default.

When offering, be specific about what you can draft and why it would help. Keep the offer brief and practical.

If drafting would be helpful:
- suggest one concrete document
- explain in one sentence what it would help the user do
- ask for only the minimum details needed to tailor it

Examples of good offers:
- Would it help if I drafted a simple meeting agenda your group could use for the first session?
- I can also draft a short email to your insurer or agency if you want something ready to send.
- If helpful, I can turn this into a checklist you can use step by step.

Avoid:
- repeating drafting offers in every response
- offering too many drafting options at once
- asking for unnecessary details
- make drafting message longer than 2-3 sentences or more than 3-4 lines long if a list.

"""

### ----------------------------------------------------------------------------------------------------
### Helpers        -
### ----------------------------------------------------------------------------------------------------

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
    if upload_resources:
        if not upload_2d_directory(chatbot_democracy_resources_directory):
            return False
        if not upload_2d_directory(chatbot_wildfire_resources_directory):
            return False
    try:
        with open("sage-resources/sage-tone.txt") as f:
            global sage_core
            sage_core = f.read()
    except:
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

    full_system_prompt = f"{sage_core}\n\n{formatting_prompt}\n\n{drafting_prompt}"

    response = sage.generate(
        model = sage_model,
        system = full_system_prompt,
        query = final_query,
        temperature = sage_temperature,
        session_id = sage_session_id,
        lastk=sage_lastk, # the citation proccess usually take three prompts, unsure if this is helpful
    )

    return response, rag_context

def get_intro():
    response, _ = prompt_sage(introduction_prompt, include_rag=False)
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
    You are generating a short 'Where this advice comes from' section for a user.

    Documents:
    {doc_summaries}

    First, write a short paragraph (2–3 sentences total) that:
    - explains what kinds of sources this advice draws from
    - describes the perspective or approach these sources take
    - clearly connects that perspective to the advice given

    Use plain, non-academic language. Do not sound like a formal citation.

    Then, underneath, include a section where you briefly provide MLA-style citations for the same sources.
    Keep these concise. Include any information you have such as author, title, date, publisher, or hyperlink.

    When constructing citations:
    - Include all relevant details when they are clearly available
    - If any information is missing, omit it cleanly
    - Do not insert placeholders such as "[No date available]"
    - Do not guess or fabricate missing details
    - Ensure each citation still reads naturally even if some fields are missing

    Requirements:
    - The paragraph should be 2–3 sentences total
    - No bullet points in the paragraph
    - MLA citations should be in a simple numbered list format
    - Do not repeat explanations in the MLA section

    Return only this output.
    """    
    response, _ = prompt_sage(citation_prompt)
    return response["result"]
    
def chat_with_sage(user_message):
    response, rag_context = prompt_sage(user_message)
    answer = response["result"]

    sources = None
    if len(rag_context) > 0:
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
        "used_rag": len(rag_context) > 0,
        "rag_context": rag_context
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
            result = chat_with_sage(usr)

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