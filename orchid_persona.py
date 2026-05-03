from build.lib.llmproxy import LLMProxy
import datetime
import sys
import pandas as pd
from civic_chatbot import CivicChatbot
from wildfire_desk import Sage

### ----------------------------------------------------------------------------------------------------
### Orchid Class
### ----------------------------------------------------------------------------------------------------

class BenchEvaluatorOrchid():
    ### ----------------------------------------------------------------------------------------------------
    ### System Settings
    ### ----------------------------------------------------------------------------------------------------

    verbose = True
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    ### ----------------------------------------------------------------------------------------------------
    ### Orchid Settings
    ### ----------------------------------------------------------------------------------------------------

    orchid = LLMProxy()
    orchid_sys = ""
    orchid_model = "4o-mini"
    orchid_temperature = 0.7
    orchid_session_id = "orchid_" + str(timestamp)
    orchid_sys_filepath = "orchid-resources/orchid-tone.txt"

    exit_eval_session_id = "orchid_early_exit_"+ str(timestamp)
    exit_eval_sys = ""
    exit_eval_filepath = "orchid-resources/exit-evaluator-tone.txt"


    def __init__(self, civic_bot:CivicChatbot):
        self.civic_bot = civic_bot


    ### ----------------------------------------------------------------------------------------------------
    ### Request and Response Helper Functions
    ### ----------------------------------------------------------------------------------------------------

    # function: prompt_orchid
    # sends a prompt to ivy and returns the model response
    def prompt_orchid(self, query_prompt, sys):
        response = self.orchid.generate(
            model=self.orchid_model,
            system=sys,
            query=query_prompt,
            temperature=self.orchid_temperature,
            session_id=self.orchid_session_id,
            lastk=5
        )
        return response
    
    def prompt_early_exit(self, query_prompt):
        response = self.orchid.generate(
            model=self.orchid_model,
            system=self.exit_eval_sys,
            query=query_prompt,
            temperature=0,
            session_id=self.exit_eval_session_id,
            lastk=0
        )
        return response

    # function: extract_response_string
    # pulls the text result out of orchid's response format
    def extract_response_string(self, response):
        if isinstance(response, dict):
            res = response.get("result")
        elif isinstance(response, tuple):
            res = response[0]["result"]
        else:
            res = response
        return res

    def setup_orchid(self):
        global orchid_sys
        try:
            self.orchid_sys = self.load_text_file(self.orchid_sys_filepath)
            self.exit_eval_sys = self.load_text_file(self.exit_eval_filepath)
        except:
            return False
        return True

    ### ----------------------------------------------------------------------------------------------------
    ### Logging Functions
    ### ----------------------------------------------------------------------------------------------------


    def log_orchid(self, file, response, verbose=verbose):
        phrase = f"Orchid: {self.extract_response_string(response)}\n"
        file.write(phrase)
        
        if verbose:
            print(phrase)

    # function: load_text_file
    # loads a text file and returns contents, handles file errors
    def load_text_file(self, filepath):
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
    
    def interpret_bot_response(self, bot_res):
        if isinstance(bot_res, tuple):
            return bot_res[0]
        elif isinstance(bot_res, str):
            return bot_res
        else:
            return "Bad return - Cannot interpret"
    
    def determine_early_exit(self, file, initial_qu, bot_responses):
        # format all the evaluation prompt
        bot_str = ""
        for resp in bot_responses:
            bot_str = bot_str + resp + "\n"
        exit_prompt = f"QUESTION : {initial_qu}\nRESPONSES : {bot_str}"
        early_exit_resp = self.prompt_early_exit(exit_prompt)
        determination = self.extract_response_string(early_exit_resp)
        early_det = "\nEarly Exit Determination: " + determination + "\n"

        file.write(early_det)
        print(early_det)

        juegement = determination.split("|")[0]
        try:
            return int(juegement) == 1
        except:    
            return 0
        
    def eval_convo(self, file, initial_qu, timeout_turns=5):
        initial_sys_inclusion = f"""\n\n**First Message Requirement (MANDATORY)**
        On your very first message only, you MUST begin with the exact phrase:

        '{initial_qu}'

        * This phrase must appear at the very start of the message
        * Do not modify or paraphrase it
        * Mandatory: Say only this phrase and nothing else"""
        initial_sys = self.orchid_sys + initial_sys_inclusion
        bot_res = ""
        orchid_responses = []
        civbot_responses = []
        for i in range(timeout_turns):
            if i == 0:
                orchid_res = self.prompt_orchid(initial_sys_inclusion, initial_sys)
            else:
                orchid_res = self.prompt_orchid(bot_res, self.orchid_sys)
            
            self.log_orchid(file, orchid_res)
            orchid_res_str = self.extract_response_string(orchid_res)

            bot_res = self.interpret_bot_response(self.civic_bot.chat_with_bot(orchid_res_str))

            self.civic_bot.log_bot(file, bot_res)
            orchid_responses.append(orchid_res_str)
            civbot_responses.append(bot_res)

            if self.determine_early_exit(file, initial_qu, civbot_responses):
                break
        
        # Add a question asking if the question was answered

        return orchid_responses, civbot_responses

    def refresh_orchid(self):
        # This just moves orchid to a completely clean session. If there is nothing in a room there isnt anything it can rememeber!
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.orchid_session_id = "orchid_" + str(self.timestamp)


### ----------------------------------------------------------------------------------------------------
### Command Line Interface
### ----------------------------------------------------------------------------------------------------


def main():
    sage = Sage()
    sage.setup_sage(False)
    orchid = BenchEvaluatorOrchid(sage)

    if not orchid.setup_orchid():
        print("An error occurred when setting up this application.")
        sys.exit(1)
    
    usr = input("What is the initial prompt for Orchid?: ")
    while usr != "quit":
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        with open(f"log-orchid-{timestamp}.txt", "w", encoding="utf-8") as file:
            file.write(f"Key Question: {usr}\n\n")
            orchid_resp, civbot_resp = orchid.eval_convo(file, usr)
            orchid.refresh_orchid()
            usr = input("What is the initial prompt for Orchid?: ")

if __name__ == "__main__":
    main()