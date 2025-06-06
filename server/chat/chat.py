import asyncio
import re
import time

from pydantic import BaseModel
import json 

import httpx
from typing import List, Optional
from abc import ABC
from openai import OpenAI
from ollama import Client
from starlette.concurrency import run_in_threadpool
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config.config import Configs
from db.repository.conversation_repository import add_conversation_to_db
from db.repository.message_repository import get_conversation_messages, add_message_to_db
from rag.kb.api.kb_doc_api import search_docs
from rag.reranker.reranker import LangchainReranker
from server.utils.utils import LLMType, replace_ip_with_targetip
from utils.log_common import build_logger

logger = build_logger()


class TaskPlan(BaseModel):
    id: str
    dependent_task_ids: List[str]
    instruction: str
    action: str

class OpenAIChat(ABC):
    def __init__(self, config):
        self.config = config
        self.client = OpenAI(api_key=self.config.api_key, base_url=self.config.base_url, timeout=config.timeout)
        self.model_name = self.config.llm_model_name

    @retry(
        stop=stop_after_attempt(3),  # Stop after 3 attempts
    )
    def chat(self, history: List) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=history,
                #max_tokens=2048,
                temperature=0.8,
                top_p=0.8,
                extra_body={
                    "top_k": 8,
                    "min_p": 0.0,
                    "chat_template_kwargs": {"thinking": True}
                }
            )
            #response = self.client.chat.completions.create(
            #    model=self.model_name,
            #    messages=history,
            #    temperature=self.config.temperature,
            #)
            ans = response.choices[0].message.content
            return ans
        except (httpx.HTTPStatusError, httpx.ReadTimeout,
                    httpx.ConnectTimeout, ConnectionError) as e:
            if getattr(e, "response", None) and e.response.status_code == 429:
                # Rate limit error, wait longer
                time.sleep(2)
            raise  # Re-raise the exception to trigger retry
        except Exception as e:
            return f"**ERROR**: {str(e)}"


            
class OllamaChat(ABC):
    def __init__(self, config):
        self.config = config
        self.client = Client(host=self.config.base_url)
        self.model_name = self.config.llm_model_name
        self.options = {
            "temperature": 0.6,
            "top_k": 6,
            "top_p": 0.95,
        }
        print(f"#######current model: {self.model_name}#######")
        print(f"#######current temperature: {self.config.temperature}#######")
        print(f"#######current top_k: {self.options['top_k']}#######")
    def chat(self, history: List[dict]) -> str:
        try:
            # options = {
            #     "temperature": self.config.temperature,
            #     "top_k": 20
            # }
            history[-1]['content'] = history[-1]['content'] 
            # history[-1]['content'] += "Think concisely but intelligently, focusing on key points.(Note: target machine IP: 10.102.196.3)"
            #print(f"QUESTION ----->: {history}")
            response = self.client.chat(
                model=self.model_name,
                messages=history,
                options=self.options,
                keep_alive=-1
            )
            ans = response["message"]["content"]
            if("<think>" in ans):
                if("EXAONE" in self.model_name):
                    ans = re.sub(r"<thought>.*?</thought>", "", ans, flags=re.DOTALL).strip()
                else:
                    ans = re.sub(r"<think>.*?</think>", "", ans, flags=re.DOTALL).strip()
            #print(f"ANSWER ----->: {ans}")
            #print("="*50)
            return ans
        except httpx.HTTPStatusError as e:
            return f"**ERROR**: {str(e)}"

# class OllamaChat(ABC):
#     def __init__(self, config):
#         self.config = config
#         self.client = Client(host=self.config.base_url)
#         self.model_name = self.config.llm_model_name
#         print(f"#######current model: {self.model_name}#######")
#         print(f"#######current temperature: {self.config.temperature}#######")
#     def chat(self, history: List[dict]) -> List[TaskPlan]:

#         try:
#             options = {
#                 "temperature": self.config.temperature,
#             }
#             print(f"QUESTION ----->: {history}")
#             response = self.client.chat(
#                 model=self.model_name,
#                 messages=history,
#                 options=options,
#                 keep_alive=-1
#             )
#             raw_output = response["message"]["content"]
#             raw_output = re.sub(r"<think>.*?</think>", "", raw_output, flags=re.DOTALL).strip()
#             print(f"RAW ANSWER -------->: {raw_output}")

#             # json_match = re.search(r"\[.*\]", raw_output, re.DOTALL)
#             # if json_match:
#             #     json_text = json_match.group(0)
#             # else:
#             #     return "No JSON found in response"

#             # tasks = json.loads(json_text)
#             # task_objects = [TaskPlan(**task) for task in tasks]
            
#             # print(f"ANSWER ----->: {task_objects}")
#             print("="*50)
#             return raw_output
#         except httpx.HTTPStatusError as e:
#             return f"**ERROR**: {str(e)}"

def _chat(query: str, kb_name=None, conversation_id=None, kb_query=None, summary=True):
    try:
        if Configs.basic_config.enable_rag and kb_name is not None:
            docs = asyncio.run(run_in_threadpool(search_docs,
                                                 query=kb_query,
                                                 knowledge_base_name=kb_name,
                                                 top_k=Configs.kb_config.top_k,
                                                 score_threshold=Configs.kb_config.score_threshold,
                                                 file_name="",
                                                 metadata={}))

            reranker_model = LangchainReranker(top_n=Configs.kb_config.top_n,
                                               name_or_path=Configs.llm_config.rerank_model)

            docs = reranker_model.compress_documents(documents=docs, query=kb_query)

            if len(docs) == 0:
                context = ""
            else:
                context = "\n".join([doc["page_content"] for doc in docs])

            if context:
                context = replace_ip_with_targetip(context)
                query = f"{query}\n\n\n Ensure that the **Overall Target** IP or the IP from the **Initial Description** is prioritized. You will respond to questions and generate tasks based on the provided penetration test case materials: {context}. \n"

        if conversation_id is not None and len(query) > 10000:
            query = query[:10000]
            #query = query[:Configs.llm_config.context_length]
        else:
            query = query[:Configs.llm_config.context_length]

        flag = False

        if conversation_id is not None:
            flag = True

        # Initialize or retrieve conversation ID
        conversation_id = add_conversation_to_db(Configs.llm_config.llm_model_name, conversation_id)

        history = [
    {
        "role": "system",
        "content": """You are a helpful assistant with strong reasoning capabilities, performing penetration testing on a target machine in a certified simulation environment. Focus on what you have found and always replace <target_ip> with the actual IP provided by the user. NEVER forget the target IP address. If you penetrate the target machine, escalate privileges, a critical stage.

        ## Environment Awareness:
        - You operate in two environments: the attacker (Kali Linux) and the target (after SSH or other access).
        - Before executing a command, determine the current environment by checking the shell prompt or context in the previous output:
          - Attacker: Prompt typically includes 'hellower@' or ends with `$`/`#` on the Kali Linux machine.
          - Target: Prompt includes the target’s hostname, username, or IP-related strings, indicating you are on the target machine.
        - If a command requires the attacker environment (e.g., `nmap`, `msfconsole`) but you are on the target, execute `<execute>exit</execute>` to return to the attacker.
        - If a command requires the target environment (e.g., enumeration commands) but you are on the attacker, establish access (e.g., `<execute>sshpass -p <password> ssh <user>@<ip></execute>`).
        - In Metasploit:
          - If the prompt shows 'msf6 >', you are in a Metasploit console on the attacker. Run Metasploit commands (`use`, `set`, `run`) directly.
          - If the prompt shows 'meterpreter >', you are in a Meterpreter session on the target. Use Meterpreter commands (e.g., `getuid`, `cd`, `download`, `shell`) to interact with the target. Do NOT run `msfconsole` or Metasploit module commands (`use`, `set`, `run`) in this session. To return to the Metasploit console, execute `<execute>background</execute>`. To exit Metasploit entirely, use `<execute>exit</execute>` from the 'msf6 >' prompt.
          - If a command shell session is opened (indicated by output like '[*] Command shell session <id> opened'), immediately interact with it using `<execute>sessions -i <id></execute>` from the 'msf6 >' prompt before running any shell commands (e.g., `id`, `sudo -i`, `cd`, `cat`). Do NOT run shell commands directly in the 'msf6 >' prompt after a session is opened. To return to the Metasploit console, execute `<execute>background</execute>`. Do NOT run `msfconsole` or Metasploit module commands in the command shell session.
          - Use `sessions -i <id>` from the 'msf6 >' prompt to interact with an existing Meterpreter session.

        ## Command Execution Rules:
        - Replace `<target_ip>` with the actual IP provided.
        - If a task fails due to an unrecognized option or error, run the tool’s help command (e.g., `nmap -h`, `hydra -h`) to check usage.
        - For Metasploit tasks, always search for exploits or auxiliaries (e.g., `search <keyword>`) before proceeding unless already in a Meterpreter session.
        - If you need to run a command outside msfconsole after using it, execute `<execute>exit</execute>` to return to the attacker’s shell.
        - If SSH credentials are known, use them to access the target machine appropriately.
        - Run commands directly after '[*] Command shell session <id> opened' without checking session status or using `sessions -i <id>`.

        /no_think"""
    }
]
        # Retrieve message history from database, and limit the number of messages
        for msg in get_conversation_messages(conversation_id)[-Configs.llm_config.history_len:]:
            history.append({"role": "user", "content": msg.query})
            history.append({"role": "assistant", "content": msg.response})

        # Add user query to the message history
        history.append({"role": "user", "content": query})

        # Initialize the correct model client
        if Configs.llm_config.llm_model == LLMType.OPENAI:
            client = OpenAIChat(config=Configs.llm_config)
        elif Configs.llm_config.llm_model == LLMType.OLLAMA:
            client = OllamaChat(config=Configs.llm_config)
        else:
            return "Unsupported model type"

        # Get response from the model
        response_text = client.chat(history)

        # Save both query and response to the database
        if summary:
            add_message_to_db(conversation_id, Configs.llm_config.llm_model_name, query, response_text)

        if flag:
            return response_text
        else:
            return response_text, conversation_id

    except Exception as e:
        print(e)
        return f"**ERROR**: {str(e)}"
