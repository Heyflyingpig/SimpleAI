import webview
import logging
import os
import json
import time
import keyboard
import threading
from PIL import Image
import pystray
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
    "default": "你是一个全能的AI助手。你的目标是提供准确、详尽且友好的回答。请在回答前仔细思考问题，并根据你的知识库提供最相关的信息。当你不确定答案时，请坦率地告知用户。你的回答应结构清晰，重点突出。",
    "paper-expert": """你是一位顶尖的学术论文翻译专家，精通中英双语，尤其擅长将中文学术内容精准翻译为符合国际学术规范的英文。
你的任务是：
1. **精准翻译**: 确保术语翻译准确无误，忠实于原文的学术语境。
2. **保持学术语气**: 使用正式、客观、严谨的学术语言。
3. **流畅自然**: 译文需符合英语母语者的学术写作习惯，避免生硬的直译。
4. **格式遵循**: 如果原文有特定的格式（如Markdown），请在译文中保留。
请专注于翻译任务，不要添加与翻译无关的评论或解释。""",
    "code-expert": """你是一位经验丰富的软件架构师和资深程序员。
你的核心职责是：
1. **代码生成**: 根据用户需求，编写高质量、可维护、遵循最佳实践（如 SOLID 原则）的代码。
2. **代码解释**: 清晰地解释代码的逻辑、关键部分的功能以及设计选择。
3. **方案设计**: 对于复杂问题，能够提出多种解决方案，并分析其优缺点。
4. **代码审查**: 能发现并指出既有代码中的潜在问题、性能瓶颈或不符合规范之处。
5. **安全意识**: 始终关注代码的安全性，避免常见的安全漏洞（如 SQL 注入、XSS 等）。
请使用 Markdown 格式来组织你的回答，代码部分使用代码块包裹并注明语言类型。""",
    "translate": """你是一位专业的翻译官，精通多种语言，尤其擅长在中文和英文之间进行转换。
你的翻译应遵循以下原则：
1. **信、达、雅**: 翻译既要忠实原文（信），又要通顺流畅（达），还要尽可能保持原文的文采和风格（雅）。
2. **语境适应**: 根据用户输入内容的上下文和可能的应用场景（如商务邮件、技术文档、日常对话、文学作品），调整翻译的风格和用词。
3. **提供备选**: 当遇到多义词或短语时，如果可能，请提供几种不同语境下的翻译建议。
4. **专注于翻译**: 请直接输出译文，除非用户特别要求，否则不要添加额外的解释或评论。"""
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
        """
        system_prompt = PROMPT_TEMPLATES.get(profile_name)
        if system_prompt:
            # 当切换 prompt 时，我们创建一个新的会话ID，以开启一段全新的对话
            self.session_id = time.strftime("%Y%m%d%H%M%S", time.localtime())
            self._create_chain(system_prompt)
            logging.info(f"Prompt profile set to '{profile_name}'. New session started: {self.session_id}")
            
            # 通知前端AI角色已经成功切换
            if self._window:
                # 使用 json.dumps 确保传递给 JS 的字符串是安全的，避免特殊字符问题
                message = json.dumps(f"AI 角色已切换为: {profile_name}")
                self._window.evaluate_js(f"addMessageToChat({message}, 'system')")
        else:
            logging.error(f"Attempted to set an unknown prompt profile: {profile_name}")


    def regenerate_response(self):
        """重新生成上一条AI回答"""
        if not hasattr(self, 'session_id'):
            logging.warning("No active session to regenerate from.")
            return

        history = SQLChatMessageHistory(
            session_id=self.session_id, connection_string="sqlite:///chat_history.db"
        )
        
        messages = history.messages
        
        # 我们需要找到最后一条人类消息。如果找不到，或者历史记录为空，则无法重新生成。
        last_user_message_content = None
        # 从后往前找，找到第一个 'human' 消息
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].type == 'human':
                # 找到了，记录下它的内容
                last_user_message_content = messages[i].content
                # 确定需要保留的消息是这条人类消息之前的所有消息
                messages_to_keep = messages[:i]
                
                # 现在，我们安全地修改数据库中的历史记录
                # 1. 清空当前会话的全部历史
                history.clear()
                # 2. 将我们想保留的消息重新加回去
                if messages_to_keep:
                    history.add_messages(messages_to_keep)
                
                # 找到后就可以跳出循环了
                break
        
        # 如果成功找到了最后的用户消息...
        if last_user_message_content:
            # ...就用它的内容重新调用 process_input
            logging.info(f"Regenerating response for: {last_user_message_content}")
            # 因为我们已经修剪了数据库中的历史记录，
            # 所以现在调用 process_input 会将这条人类消息和新的AI回答追加到正确的历史末尾。
            self.process_input(last_user_message_content)
        else:
            # 如果循环结束都没找到，说明历史记录里一条用户消息都没有
            logging.warning("Could not find the last user message to regenerate.")
            if self._window:
                message = json.dumps("没有可以重新生成的消息。")
                self._window.evaluate_js(f"addMessageToChat({message}, 'system')")

    ## 前端调用
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
window = None
# 我们用自己的变量来追踪窗口状态
is_window_visible = False
# 全局变量，用于持有托盘图标对象
tray_icon = None


def quit_app():
    """安全地退出整个应用程序。"""
    logging.info("Quit command received. Shutting down.")
    if tray_icon:
        tray_icon.stop()
    if window:
        # 确保在主GUI线程中销毁窗口
        window.destroy()
    # 使用 os._exit(0) 来强制终止整个进程，包括所有后台线程
    os._exit(0)


def on_closing():
    """当用户点击关闭按钮时，隐藏窗口而不是退出。"""
    global is_window_visible
    if window:
        window.hide()
        # 手动更新我们自己的状态变量
        is_window_visible = False
    # 返回 False 会取消默认的关闭事件，从而阻止应用退出
    # 如果希望在某些情况下（例如从托盘菜单选择退出）能真正关闭，可以在这里加入判断逻辑
    return False 

def toggle_window():
    """根据窗口当前状态，显示或隐藏窗口。"""
    global is_window_visible
    if not window:
        return
    
    try:
        # 使用我们自己的状态变量来判断
        if not is_window_visible:
            logging.info("Window state is 'hidden', showing it.")
            window.show()
            is_window_visible = True
        else:
            logging.info("Window state is 'visible', hiding it.")
            window.hide()
            is_window_visible = False
    except Exception as e:
        # 如果窗口已经被销毁，可能会抛出异常
        logging.error(f"Error toggling window: {e}")

def setup_tray():
    """设置并运行系统托盘图标。"""
    global tray_icon
    try:
        image_path = os.path.join(base_path, "static", "img", "icon.png")
        image = Image.open(image_path)
    except FileNotFoundError:
        logging.error(f"Icon file not found at {image_path}. Please ensure it exists.")
        return

    # 定义菜单项
    menu = (
        pystray.MenuItem('显示/隐藏', toggle_window, default=True),
        pystray.MenuItem('退出', quit_app),

    )

    # 创建托盘图标
    tray_icon = pystray.Icon("SimpleAI", image, "SimpleAI", menu)
    logging.info("System tray icon is running.")
    # 这会阻塞，直到调用 icon.stop()
    tray_icon.run()


def start_keyboard_listener():
    """启动全局快捷键监听。"""
    # 设置你想要的快捷键，这里使用 Ctrl+Shift+A 作为例子
    # 'a' 可以换成任何你想要的字母或按键
    hotkey = "ctrl+shift+a"
    keyboard.add_hotkey(hotkey, toggle_window)
    logging.info(f"Hotkey '{hotkey}' registered. Waiting for hotkey presses...")
    # 这会阻塞，直到程序退出，所以它需要在自己的线程中运行
    keyboard.wait()


def post_start(w):
    """
    该函数会在 webview.start() 之后，在独立的线程中执行
    这是把 window 对象安全地传递给 API 实例的最佳时机
    """
    global window, is_window_visible
    window = w
    api._window = window
    # 窗口初始是可见的，所以我们在这里同步状态
    is_window_visible = True
    logging.info("Window object has been successfully assigned to the API.")

    # 启动快捷键监听线程
    listener_thread = threading.Thread(target=start_keyboard_listener, daemon=True)
    listener_thread.start()
    logging.info("Keyboard listener thread started.")

    # 启动系统托盘图标线程
    tray_thread = threading.Thread(target=setup_tray, daemon=True)
    tray_thread.start()
    logging.info("System tray thread started.")


def main_display():
    global window
    # 我们将创建的窗口实例直接赋值给全局变量
    window = webview.create_window("SimpleAI", "static/index.html", height=600,width=400, js_api = api, on_top=True)
    # 订阅 closing 事件。当用户尝试关闭窗口时，会调用 on_closing 函数
    window.events.closing += on_closing
    logging.info("窗口创建成功")
    webview.start(post_start, window, debug=True)

if __name__ == "__main__":
    main_display()