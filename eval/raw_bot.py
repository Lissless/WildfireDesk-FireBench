from civic_chatbot import CivicChatbot
from build.lib.llmproxy import LLMProxy
import datetime

class RawBot(CivicChatbot):
    rchatgpt = LLMProxy()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    chat_general_session_id = "chat_general_" + str(timestamp)
    model = ""

    def __init__(self, model):
        self.model = model

    def chat_with_bot(self, query_prompt):
        response = self.rchatgpt.generate(
            model=self.model,
            system="Answer the question in any way you see fit.",
            query=query_prompt,
            session_id=self.chat_general_session_id,
        )

        return response["result"]

    def log_bot(self, file, response):
        phrase = ""

        if isinstance(response, dict):
            phrase = f"""ChatGPT: {response.get("result")}\n"""
        elif isinstance(response, tuple):
            phrase = f"""ChatGPT: {response[0]["result"]}\n"""
        else:
            phrase = f"""ChatGPT: {response}\n"""

        file.write(phrase)

    def add_model(self, model):
        choices = ["gpt-4.1-mini, gpt-5-mini, gpt-5-nano, 4o-mini, us.meta.llama4-maverick-17b-instruct-v1:0, us.meta.llama4-scout-17b-instruct-v1:0, us.meta.llama3-2-90b-instruct-v1:0, us.meta.llama3-3-70b-instruct-v1:0, us.meta.llama3-2-3b-instruct-v1:0, us.meta.llama3-2-1b-instruct-v1:0, us.meta.llama3-1-8b-instruct-v1:0, us.anthropic.claude-3-haiku-20240307-v1:0, google.gemma-3-4b-it, google.gemma-3-12b-it, google.gemma-3-27b-it, gemini-2.5-flash-lite"]
        if model not in choices:
            print("Invalid Choice")
            return
        self.model = model
        # get a clean session
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.chat_general_session_id = "chat_general_" + str(self.timestamp)



    
