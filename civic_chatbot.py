from abc import ABC, abstractmethod

### ----------------------------------------------------------------------------------------------------
### Civic Chatbot Class
### ----------------------------------------------------------------------------------------------------

class CivicChatbot(ABC):
    #must at least return the response first
    @abstractmethod
    def chat_with_bot(query_prompt):
        pass

    @abstractmethod
    def log_bot(response):
        pass
        

    # def 

    
