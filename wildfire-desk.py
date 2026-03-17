from build.lib.llmproxy import LLMProxy
import time
import datetime
import sys
# I advocate for the name Sage for this bot
#   - its a plant that grows in dry areas such as California which is a huge target for wildfires
#   - its a name associated with wisdom and protection

### ----------------------
### System Settings        -
### ----------------------

timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
verbose = True
display_rag = True

### ----------------------
### Sage Settings        -
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

    return response
    
# returns if this was successful or not
def setup_sage():
    # upload and store the string contents of the tone 
    if not upload_to_sage("sage-resources/question-types.pdf"):
        return False
    try:
        with open("sage-resources/sage-tone.txt") as f:
            global sage_core
            sage_core = f.read()
    except:
        return False
    return True

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
    if(display_rag):
        print(f"""\n******************\nRag_context: {len(response["rag_context"])} \n******************\n\n""")

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
        log_user(file, usr)
        while usr != "quit":
            resp = prompt_sage(usr)
            log_sage(file, resp)
            usr = input("Type your response here: ")
            log_user(file, usr)

if __name__ == '__main__':
    main()
