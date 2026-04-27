from abc import ABC, abstractmethod

### ----------------------------------------------------------------------------------------------------
### Civic Chatbot Class
### ----------------------------------------------------------------------------------------------------

class CivicChatbot(ABC):
    #must at least return the response first, this response must be a String
    @abstractmethod
    def chat_with_bot(self, query_prompt):
        pass

    @abstractmethod
    def log_bot(self, file, response):
        pass
        

    # def 

    
