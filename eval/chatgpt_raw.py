from civic_chatbot import CivicChatbot
from build.lib.llmproxy import LLMProxy
import datetime

class RawChatGPT(CivicChatbot):
    rchatgpt = LLMProxy()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    chat_general_session_id = "chat_general_" + str(timestamp)

    def chat_with_bot(self, query_prompt):
        response = self.rchatgpt.generate(
            model="4o-mini",
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
