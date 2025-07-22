import webview
import logging
import os
import json
import time
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(levelname)s - %(message)s')

base_path = os.path.dirname(__file__)
secret_path = os.path.join(base_path, "secrets.json")
with open(secret_path, "r") as f:
    secret = json.load(f)
model_name = secret["model_name"]
api_key = secret["api_key"]
base_url = secret["base_url"]


PROMPT_TEMPLATES = {
    "paper-expert": "你是一个得力的论文翻译助手助手",
    "code-expert": "你是一个专业的程序员，会根据用户的问题，生成高质量的代码，并附带代码解释",
    "translate": "你是一个专业的翻译家，可以将用户输入的内容翻译成英文"
}


class Api:
    def __init__(self):
        self._window = None
        # 1. 初始化 LLM, 作为类的属性，方便复用
        self.llm = ChatOpenAI(model=model_name, api_key=api_key, base_url=base_url)
        # 2. 使用默认的 prompt 初始化
        self.set_prompt_profile("default")

    def _create_chain(self, system_prompt):
        """
        一个私有方法，用于根据提供的 system_prompt 创建一个完整的、带历史记录的 chain。
        将其独立出来，方便在切换 prompt 时重复调用。
        """
        # 1. 基于传入的 system_prompt 创建 Prompt Template
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}"),
            ]
        )
        
        # 2. 创建基础的 Chain
        chain = prompt | self.llm
        
        # 3. 创建带历史记录的 Chain
        self.chain_with_history = RunnableWithMessageHistory(
            chain,
            lambda session_id: SQLChatMessageHistory(
                session_id=session_id, connection_string="sqlite:///chat_history.db"
            ),
            input_messages_key="question",
            history_messages_key="history",
        )

    def set_prompt_profile(self, profile_name="default"):
        """
        这是一个可以被JavaScript调用的公共方法。
        它会根据传入的 profile_name 从 PROMPT_TEMPLATES 字典中查找对应的 system_prompt，
        然后创建一个新的 chain，并开启一个全新的会话。
        这样做可以确保不同角色的对话历史是相互隔离的。
        """
        system_prompt = PROMPT_TEMPLATES.get(profile_name)
        if system_prompt:
            # 当切换 prompt 时，我们创建一个新的会话ID，以开启一段全新的对话
            self.session_id = time.strftime("%Y%m%d%H%M%S", time.localtime())
            self._create_chain(system_prompt)
            logging.info(f"Prompt profile set to '{profile_name}'. New session started: {self.session_id}")
            
            # (可选功能) 通知前端AI角色已经成功切换
            if self._window:
                # 使用 json.dumps 确保传递给 JS 的字符串是安全的，避免特殊字符问题
                message = json.dumps(f"AI 角色已切换为: {profile_name}")
                self._window.evaluate_js(f"addMessageToChat({message}, 'system')")
        else:
            logging.error(f"Attempted to set an unknown prompt profile: {profile_name}")

    def process_input(self, text):
        """这个方法会被 JS 调用"""
        logging.info(f"Python 收到了来自 JS 的消息: {text}")
        
        # 调用 LangChain 并传入 session_id
        try:
            response = self.chain_with_history.invoke(
                {"question": text},
                config={"configurable": {"session_id": self.session_id}}
            )
            logging.info(f"LangChain 响应: {response.content}")
        except Exception as e:
            logging.error(f"LangChain 调用失败: {str(e)}")
            return  # 提前返回，避免后续错误
        
        response_text = response.content

        if self._window:
            # 使用 json.dumps 为 JS 安全地转义字符串，这能正确处理引号、换行符等
            js_response_text = json.dumps(response_text)
            try:
                # 注意 js_response_text 已经包含了引号，所以 f-string 中不再需要额外的引号
                self._window.evaluate_js(f"addMessageToChat({js_response_text}, 'ai')")
                logging.info("成功调用 evaluate_js，已将AI响应发送到前端。")
            except Exception as e:
                logging.error(f"evaluate_js 调用失败: {str(e)}")


api = Api()


def post_start(window):
    """
    该函数会在 webview.start() 之后，在独立的线程中执行
    这是把 window 对象安全地传递给 API 实例的最佳时机
    """
    api._window = window
    logging.info("Window object has been successfully assigned to the API.")

def main_display():
    window = webview.create_window("SimpleAI", "static/index.html", height=600,width=400, js_api = api)
    logging.info("窗口创建成功")
    webview.start(post_start, window, debug=True)

if __name__ == "__main__":
    main_display()