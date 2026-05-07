from build.lib.llmproxy import LLMProxy
import time
import datetime
import sys
from string import Template
from pathlib import Path
from ivy_crawl import search_web, get_state_to_communities_map
from civic_chatbot import CivicChatbot

### ----------------------------------------------------------------------------------------------------
### System Settings
### ----------------------------------------------------------------------------------------------------

chatbot_democracy_resources_directory = "sage-resources/democracy-chatbot-resources"
chatbot_wildfire_resources_directory = "sage-resources/wildfire-resources"
sage_instructions_directory = "sage-resources/sage-instructions"
upload_resources_flag = False

class Sage(CivicChatbot):
    ### ----------------------------------------------------------------------------------------------------
    ### Sage Settings
    ### ----------------------------------------------------------------------------------------------------

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    verbose = True
    display_rag = 0
    
    sage = LLMProxy()
    sage_tone = ""
    sage_interaction = ""
    sage_formatting = ""
    sage_drafting = ""
    sage_guardrails = ""
    sage_intro = ""
    sage_privacy = ""
    sage_model = "4o-mini"
    sage_temperature = 0.6
    sage_grounded_session_id = "sage_grounded_" + str(timestamp)
    sage_general_session_id = "sage_general_" + str(timestamp)
    sage_RAG_id = "sage_rag2"
    sage_rag_t = 0.4
    sage_rag_k = 5
    sage_intro_session_id = "sage_intro_" + str(timestamp)

    def __init__(self, setup=True):
        self.setup_sage(setup)

    ### ----------------------------------------------------------------------------------------------------
    ### Core Chat Functions
    ### ----------------------------------------------------------------------------------------------------

    # function: chat_with_bot
    # runs main chat flow and combines rag, ivy results, citations, and followups
    def chat_with_bot(self, user_message, mode="grounded", use_local_news=False, selected_state="", selected_community=""):
        use_rag = (mode == "grounded")

        web_results = []
        if use_local_news and selected_state:
            try:
                web_results = search_web(user_message, selected_state, selected_community)
            except Exception as e:
                print("Web search error:", e)

        web_context = self.format_web_results_for_prompt(web_results)

        response, rag_context = self.prompt_sage(
            user_message,
            include_rag=use_rag,
            web_context=web_context
        )
        answer = response["result"]

        sources = None
        show_citations = self.should_show_citations(answer)
        should_generate = self.should_generate_followups(answer)

        rag_sources = None
        web_sources = None

        if show_citations:
            if use_rag and len(rag_context) > 0:
                rag_sources = self.get_source(rag_context)

            if len(web_results) > 0:
                web_sources = self.get_web_sources(web_results)

            if rag_sources and web_sources:
                sources = f"{rag_sources}\n{web_sources}"
            elif rag_sources:
                sources = rag_sources
            elif web_sources:
                sources = web_sources

        elif not use_rag and should_generate:
            warning = (
                "Note: This answer is based on general knowledge and may not reflect "
                "specific local policies or up-to-date recovery information. "
                "You may want to verify details with local agencies."
            )
            answer = f"{answer}\n\n---\n{warning}"

        followups = []
        if should_generate:
            followups = self.get_followup_questions(user_message, answer)

        return answer, {
            "answer": answer,
            "sources": sources,
            "followups": followups,
            "web_results": web_results
        }
    
    # function: build_sage_system_prompt
    # combines all instruction files into one system prompt
    def build_sage_system_prompt(self):
        return "\n\n".join([
            self.sage_tone,
            self.sage_interaction,
            self.sage_formatting,
            self.sage_drafting,
            self.sage_guardrails,
            self.sage_privacy
        ])


    # function: get_sage_session_id
    # picks the grounded or general session id
    def get_sage_session_id(self, include_rag=True):
        if include_rag:
            return self.sage_grounded_session_id
        return self.sage_general_session_id


    # function: rag_context_string_simple
    # formats rag results into plain text for the prompt
    def rag_context_string_simple(self, rag_context):
        context_string = ""
        i = 1

        for collection in rag_context:
            if not context_string:
                context_string = "The following is additional context that may be helpful in answering the user's query."

            context_string += """
            #{} {}
            """.format(i, collection["doc_summary"])

            j = 1
            for chunk in collection["chunks"]:
                context_string += """
                #{}.{} {}
                """.format(i, j, chunk)
                j += 1
            i += 1

        return context_string


    # function: parse_retrieve_rag_context
    # turns rag results into a numbered summary list
    def parse_retrieve_rag_context(self, rag_ctx):
        summaries = ""
        index = 1

        for rec in rag_ctx:
            summaries += f"""{str(index)}. {rec["doc_summary"]}\n"""
            index += 1

        return summaries, index

    ### ----------------------------------------------------------------------------------------------------
    ### Web Context and Source Formatting Functions
    ### ----------------------------------------------------------------------------------------------------

    # function: format_web_results_for_prompt
    # formats ivy results into readable text for sage input
    def format_web_results_for_prompt(self, web_results):
        if not web_results:
            return ""

        lines = ["The following recent local news context may be relevant to the user's question:"]

        for i, record in enumerate(web_results, start=1):
            outlet = record.get("Outlet", "")
            url = record.get("URL", "")
            info = record.get("Info", "")
            timestamp_value = record.get("Timestamp", "")

            lines.append(
                f"{i}. Outlet: {outlet}\n"
                f"   Timestamp: {timestamp_value}\n"
                f"   URL: {url}\n"
                f"   Relevant information: {info}"
            )

        return "\n".join(lines)


    # function: get_web_sources
    # converts ivy results into citation text for the frontend
    def get_web_sources(self, web_results):
        if not web_results:
            return None

        intro = (
            "This answer also draws from recent local news coverage that may be relevant "
            "to the user's question."
        )

        lines = [intro]
        for i, record in enumerate(web_results, start=1):
            outlet = record.get("Outlet", "").strip()
            url = record.get("URL", "").strip()
            timestamp = record.get("Timestamp", "").strip()

            citation = outlet
            if timestamp:
                citation += f". {timestamp}."
            if url:
                citation += f" {url}"

            lines.append(f"{i}. {citation}")

        return "\n".join(lines)

    ### ----------------------------------------------------------------------------------------------------
    ### Sage Upload and Setup Functions
    ### ----------------------------------------------------------------------------------------------------

    # function: upload_to_sage
    # uploads one file into sage's rag store
    def upload_to_sage(self, filepath):
        response = self.sage.upload_file(
            file_path=filepath,
            session_id=self.sage_RAG_id,
            strategy="smart"
        )
        time.sleep(3)

        if "result" not in response:
            print("Resource upload error\n")
            print("Full response:", response)
            return False

        resp_message = response["result"]

        if self.verbose and self.display_rag > 0:
            fileparts = str(filepath).split("/")
            name = fileparts[len(fileparts) - 1]
            print("Upload Status: " + resp_message + ", Filename: " + name)
        elif self.verbose:
            print("Upload Status: " + resp_message)

        return resp_message == "success"


    # function: upload_2d_directory
    # uploads files from a directory into sage's rag store
    def upload_2d_directory(self, filepath_str):
        p = Path(filepath_str)

        for data in p.iterdir():
            if data.is_dir():
                for file in data.iterdir():
                    if not self.upload_to_sage(file.relative_to(".")):
                        print(f"""File: {file.name} - failed to upload\n""")
                        return False
            elif data.is_file():
                if not self.upload_to_sage(data.relative_to(".")):
                    print(f"""File: {data.name} - failed to upload\n""")
                    return False

        return True


    # function: setup_sage
    # loads sage instruction files and prepares the app
    def setup_sage(self, upload_resources=True):
        # global sage_tone
        # global sage_interaction
        # global sage_formatting
        # global sage_drafting
        # global sage_guardrails
        # global sage_intro
        # global sage_privacy

        if upload_resources:
            if not self.upload_2d_directory(chatbot_democracy_resources_directory):
                return False
            if not self.upload_2d_directory(chatbot_wildfire_resources_directory):
                return False

        # try:
        self.sage_tone = self.load_text_file(f"{sage_instructions_directory}/sage-tone.txt")
        self.sage_interaction = self.load_text_file(f"{sage_instructions_directory}/sage-interaction.txt")
        self.sage_formatting = self.load_text_file(f"{sage_instructions_directory}/sage-formatting.txt")
        self.sage_drafting = self.load_text_file(f"{sage_instructions_directory}/sage-drafting.txt")
        self.sage_guardrails = self.load_text_file(f"{sage_instructions_directory}/sage-guardrails.txt")
        self.sage_intro = self.load_text_file(f"{sage_instructions_directory}/sage-introduction.txt")
        self.sage_privacy = self.load_text_file(f"{sage_instructions_directory}/sage-privacy.txt")
        # except Exception:
        #     return False
        
        

        if (
            self.sage_tone is None or
            self.sage_interaction is None or
            self.sage_formatting is None or
            self.sage_drafting is None or
            self.sage_guardrails is None or
            self.sage_intro is None or
            self.sage_privacy is None
        ):
            print("One or more of sage's instructions failed to load.")
            return False

        return True

    ### ----------------------------------------------------------------------------------------------------
    ### Sage Generation and Citation Functions
    ### ----------------------------------------------------------------------------------------------------

    # function: prompt_sage
    # sends a query to sage and optionally includes rag and web context
    def prompt_sage(self, query_prompt, include_rag=True, web_context="",):
        final_query = ""
        rag_context = []

        if include_rag:
            rag_context = self.sage.retrieve(
                query=query_prompt,
                session_id=self.sage_RAG_id,
                rag_threshold=self.sage_rag_t,
                rag_k=self.sage_rag_k
            )

            final_query = Template("$query\n$rag_context\n$web_context").substitute(
                query=query_prompt,
                rag_context=self.rag_context_string_simple(rag_context),
                web_context=web_context
            )
        else:
            final_query = Template("$query\n$web_context").substitute(
                query=query_prompt,
                web_context=web_context
            )

        full_system_prompt = self.build_sage_system_prompt()
        active_session_id = self.get_sage_session_id(include_rag=include_rag)

        response = self.sage.generate(
            model=self.sage_model,
            system=full_system_prompt,
            query=final_query,
            temperature=self.sage_temperature,
            session_id=active_session_id,
            lastk=3,
        )

        return response, rag_context


    # function: get_intro
    # generates sage's intro message
    def get_intro(self):
        full_system_prompt = self.build_sage_system_prompt()

        response = self.sage.generate(
            model=self.sage_model,
            system=full_system_prompt,
            query=self.sage_intro,
            temperature=self.sage_temperature,
            session_id=self.sage_intro_session_id,
            lastk=0,
        )

        return response["result"]


    # function: get_source
    # generates a citation summary from rag context using sage
    def get_source(self, rag_context):
        doc_summaries, _ = self.parse_retrieve_rag_context(rag_context)

        citation_prompt = f"""
        You are generating a short "Where this advice comes from" section for a user.

        Documents:
        {doc_summaries}

        Write the output in TWO parts:

        PART 1 — SUMMARY PARAGRAPH
        Write a 2 sentences that:
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
        - Include only information that is explicitly available in the provided document summaries
        - If a hyperlink is explicitly available, include it in the citation
        - If a date is explicitly available, include it in the citation
        - If a hyperlink is not available, omit it
        - If a date is not available, omit it
        - Never write placeholders such as "[No date available]" or "[No link available]"
        - Never invent or guess missing information
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
        response, _ = self.prompt_sage(citation_prompt)
        return response["result"]

    ### ----------------------------------------------------------------------------------------------------
    ### Response Classification Functions
    ### ----------------------------------------------------------------------------------------------------

    # function: should_show_citations
    # decides if the current sage answer should show sources
    def should_show_citations(self, answer):
        cleaned = answer.strip()

        if len(cleaned) > 300:
            return True
        if "1." in cleaned or "2." in cleaned or "- " in cleaned:
            return True
        if len(cleaned) < 300 and cleaned.count("?") >= 2:
            return False

        evaluation_prompt = f"""
        You are classifying Sage's response.

        Sage response:
        {answer}

        Return exactly one word:

        YES = this response contains a substantive answer or guidance that should display citations
        NO = this response is mainly asking the user clarifying questions and should not display citations

        Rules:
        - Return YES if Sage gives meaningful advice, steps, explanation, or guidance, even if it ends with one brief follow-up offer or question
        - Return NO only if Sage is mainly waiting for the user to clarify or answer questions before providing guidance
        - Return only YES or NO
        """

        response, _ = self.prompt_sage(evaluation_prompt, include_rag=False)
        decision = response["result"].strip().upper()
        return decision == "YES"


    # function: should_generate_followups
    # decides if the ui should show suggested follow-up questions
    def should_generate_followups(self, answer):
        cleaned = answer.strip()
        lowered = cleaned.lower()

        clarification_signals = [
            "if it's easy, you can share:",
            "if it’s easy, you can share:",
            "it would help to know",
            "what's your",
            "what’s your",
            "can you share",
            "can you tell me",
            "please provide",
            "please share",
            "i can help with that",
        ]

        if any(signal in lowered for signal in clarification_signals):
            return False

        if len(cleaned) > 450 and cleaned.count("?") <= 1:
            return True

        evaluation_prompt = f"""
        You are classifying Sage's response.

        Sage response:
        {answer}

        Decide whether the system should suggest follow-up questions that the USER might ask next.

        Return exactly one word:
        YES or NO

        Rules:
        - Return YES if Sage provides a substantive answer, steps, explanation, or guidance
        - Return YES even if Sage ends with one brief optional question or offer
        - Return NO if Sage is primarily asking the user for clarification before giving a real answer
        - Return NO if the response is mostly questions and lacks meaningful guidance
        - Return NO for structured intake prompts that ask the user to fill in details

        Return only YES or NO.
        """
        response, _ = self.prompt_sage(evaluation_prompt, include_rag=False)
        return response["result"].strip().upper() == "YES"


    # function: get_followup_questions
    # generates 2 likely next questions from the user's perspective
    def get_followup_questions(self, user_message, answer):
        followup_prompt = f"""
        You are simulating what the USER is likely thinking after reading an answer.

        User's original question:
        {user_message}

        Sage's response:
        {answer}

        Write exactly 2 follow-up questions that the USER would naturally ask next.

        Guidelines:
        - These should reflect the user's perspective, not the assistant's
        - Make them specific to the situation described in the answer
        - Focus on what the user would realistically want to clarify, decide, or do next
        - Use natural, conversational phrasing
        - Avoid formal or advisory language
        - Do not suggest what the user "should" do
        - Do not sound like an expert or assistant
        - Each question should feel like a direct continuation of the user's thinking

        Output rules:
        - Exactly 2 questions
        - Each on its own line
        - No numbering, no bullets, no extra text
        """

        response, _ = self.prompt_sage(followup_prompt, include_rag=False)
        raw_text = response["result"].strip()

        questions = []
        for line in raw_text.splitlines():
            cleaned = line.strip().lstrip("-•1234567890. ").strip()
            if cleaned and "?" in cleaned:
                questions.append(cleaned)

        if len(questions) < 2:
            questions = []
            parts = raw_text.split("?")
            for part in parts:
                cleaned = part.strip().lstrip("-•1234567890. ").strip()
                if cleaned:
                    questions.append(cleaned + "?")

        questions = [q for q in questions if q.strip()]

        if len(questions) >= 2:
            return questions[:2]

        return [
            "What should I do first?",
            "Can you help me turn that into a message or agenda?"
        ]
    
    ### ----------------------------------------------------------------------------------------------------
    ### File and Prompt Helper Functions
    ### ----------------------------------------------------------------------------------------------------

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

    ### ----------------------------------------------------------------------------------------------------
    ### Logging Functions, Assess Question
    ### ----------------------------------------------------------------------------------------------------

    # function: log_user
    # writes the user's message to the log and prints it if verbose
    def log_user(self, file, text, verbose=verbose):
        phrase = "Anon: " + text + "\n\n"
        file.write(phrase)

        if verbose:
            print(phrase)

    # function: log_bot
    # writes sage's response to the log and can print rag debug info
    def log_bot(self, file, response, rag_context="", verbose=verbose, display_rag=display_rag):
        phrase = ""

        if isinstance(response, dict):
            phrase = f"""Sage: {response.get("result")}\n"""
        elif isinstance(response, tuple):
            phrase = f"""Sage: {response[0]["result"]}\n"""
        else:
            phrase = f"""Sage: {response}\n"""

        file.write(phrase)

        if verbose:
            print(phrase)

        if display_rag == 1:
            print(f"""\n******************\nRag_context: {rag_context} \nRag_context_length: {len(rag_context)} \n******************\n\n""")
        elif display_rag == 2:
            print(f"""\n******************\nRag_context_length: {len(rag_context)} \n******************\n\n""")


    ### ----------------------------------------------------------------------------------------------------
    ### Getters and Setters
    ### ----------------------------------------------------------------------------------------------------

    def get_timestamp(self):
        return self.timestamp
    
    def set_verbose(self, verb):
        self.verbose = verb

    def set_display_rag(self, dr_val):
        self.display_rag = dr_val
    

### ----------------------------------------------------------------------------------------------------
### Command Line Interface
### ----------------------------------------------------------------------------------------------------

# function: run_cli
# runs the command line version of the chatbot
def run_cli():
    sage = Sage()
    if not sage.setup_sage(upload_resources_flag):
        print("An error occurred when setting up this application.")
        sys.exit(1)

    with open(f"log-{sage.get_timestamp()}.txt", "w", encoding="utf-8") as file:
        intro = sage.get_intro()
        sage.log_bot(file, intro)

        usr = input("Type your response here: ")

        while usr != "quit":
            sage.log_user(file, usr)

            answer, result = sage.chat_with_bot(usr, mode="grounded")

            sage.log_bot(file, answer, result.get("rag_context", []))

            if result["sources"]:
                print("\nCitation Summary:\n")
                sage.log_bot(file, result["sources"])
            else:
                print("WARNING: No vetted resources were used to produce the information above")

            usr = input("Type your response here: ")


if __name__ == "__main__":
    run_cli()