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
prompt_path = os.path.join(base_path, "prompts.json") # 新增 prompts.json 路径

# 检查配置文件是否存在，如果不存在则创建一个默认的
if not os.path.exists(secret_path):
    logging.warning("secrets.json not found, creating a default one.")
    default_secrets = {
        "model_name": "",
        "api_key": "",
        "base_url": "",
        "hotkey": "ctrl+shift+a"
    }
    with open(secret_path, 'w', encoding='utf-8') as f:
        json.dump(default_secrets, f, indent=4)


class Api:
    def __init__(self):
        self._window = None
        self.settings = self.get_settings()
        self.prompts = self.get_prompts() # 加载所有提示词
        # 1. 初始化 LLM, 作为类的属性，方便复用
        self.llm = ChatOpenAI(
            model=self.settings.get("model_name"), 
            api_key=self.settings.get("api_key"), 
            base_url=self.settings.get("base_url")
        )
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

    def get_settings(self):
        """从 secrets.json 加载设置并返回一个字典。"""
        try:
            with open(secret_path, "r", encoding='utf-8') as f:
                settings = json.load(f)
                logging.info(f"Settings loaded: {settings}")
                return settings
        except Exception as e:
            logging.error(f"Could not load settings from {secret_path}: {e}")
            return {} # 返回空字典以避免崩溃

    def save_settings(self, settings_data):
        """从前端接收一个字典并将其保存到 secrets.json。"""
        try:
            # 在保存前，确保所有必要的键都存在
            current_settings = self.get_settings()
            current_settings.update(settings_data)

            with open(secret_path, "w", encoding='utf-8') as f:
                json.dump(current_settings, f, indent=4)
            logging.info(f"Settings saved: {current_settings}")
            
            # 保存后，重新加载 LLM 以应用新设置
            self.settings = current_settings
            self.llm = ChatOpenAI(
                model=self.settings.get("model_name"),
                api_key=self.settings.get("api_key"),
                base_url=self.settings.get("base_url")
            )
            logging.info("LLM re-initialized with new settings.")
        except Exception as e:
            logging.error(f"Could not save settings to {secret_path}: {e}")
    
    def get_prompts(self):
        """从 prompts.json 加载所有提示词。"""
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Could not load prompts from {prompt_path}: {e}")
            return {}

    def save_prompt(self, prompt_id, name, prompt_text):
        """新增或更新一个提示词并保存到文件。"""
        try:
            # 使用 slugify 创建一个对文件名和URL友好的ID
            from slugify import slugify
            if not prompt_id: # 如果是新增
                prompt_id = slugify(name) if name else f"prompt-{int(time.time())}"
            
            self.prompts[prompt_id] = {"name": name, "prompt": prompt_text}
            with open(prompt_path, 'w', encoding='utf-8') as f:
                json.dump(self.prompts, f, indent=4, ensure_ascii=False)
            
            logging.info(f"Prompt '{prompt_id}' saved.")
            return {"success": True, "prompts": self.prompts}
        
        except Exception as e:
            
            logging.error(f"Failed to save prompt '{prompt_id}': {e}")
            return {"success": False, "error": str(e)}

    def delete_prompt(self, prompt_id):
        """删除一个提示词。"""
        try:
            if prompt_id in self.prompts and prompt_id != "default":
                del self.prompts[prompt_id]
                with open(prompt_path, 'w', encoding='utf-8') as f:
                    json.dump(self.prompts, f, indent=4, ensure_ascii=False)
                logging.info(f"Prompt '{prompt_id}' deleted.")
                return {"success": True, "prompts": self.prompts}
            else:
                logging.warning(f"Attempted to delete non-existent or default prompt '{prompt_id}'.")
                return {"success": False, "error": "Cannot delete default or non-existent prompt."}
        except Exception as e:
            logging.error(f"Failed to delete prompt '{prompt_id}': {e}")
            return {"success": False, "error": str(e)}

    def change_hotkey(self, new_hotkey):
        """动态更改并保存快捷键。"""
        global hotkey
        try:
            logging.info(f"Attempting to change hotkey from '{hotkey}' to '{new_hotkey}'")
            # 1. 移除旧的快捷键
            keyboard.remove_hotkey(hotkey)
            # 2. 添加新的快捷键
            keyboard.add_hotkey(new_hotkey, toggle_window)
            # 3. 更新全局变量
            hotkey = new_hotkey
            # 4. 更新并保存到配置文件
            self.settings['hotkey'] = new_hotkey
            self.save_settings(self.settings)
            logging.info(f"Successfully changed hotkey to '{new_hotkey}'")
        except Exception as e:
            logging.error(f"Failed to change hotkey: {e}")
            # 如果失败了，尝试恢复旧的快捷键
            keyboard.add_hotkey(hotkey, toggle_window)

    
    def set_prompt_profile(self, profile_name="default"):
        """
        这是一个可以被JavaScript调用的公共方法。
        它会根据传入的 profile_name 从 PROMPT_TEMPLATES 字典中查找对应的 system_prompt，
        """
        # 现在从加载的 prompts 字典中获取
        prompt_data = self.prompts.get(profile_name)
        if prompt_data and 'prompt' in prompt_data:
            system_prompt = prompt_data['prompt']
            # 当切换 prompt 时，我们创建一个新的会话ID，以开启一段全新的对话
            self.session_id = time.strftime("%Y%m%d%H%M%S", time.localtime())
            self._create_chain(system_prompt)
            logging.info(f"Prompt profile set to '{profile_name}'. New session started: {self.session_id}")
            
            # 通知前端AI角色已经成功切换
            if self._window:
                # 使用 json.dumps 确保传递给 JS 的字符串是安全的，避免特殊字符问题
                message = json.dumps(f"AI 角色已切换为: {prompt_data.get('name', profile_name)}")
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
            if self._window:
                # 构造一个用户友好的错误消息，并将其发送到前端
                error_message = f"抱歉，AI 响应失败。\n请检查您的网络连接和 API 设置是否正确。如果您是首次使用本软件，请右键托盘的设置选项，进行配置。\n错误详情: {e}"
                js_error_message = json.dumps(error_message)
                try:
                    self._window.evaluate_js(f"addMessageToChat({js_error_message}, 'system')")
                except Exception as eval_e:
                    logging.error(f"向前端发送错误消息失败: {eval_e}")
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
# 全局变量，用于持有设置窗口对象，确保只有一个实例
settings_window = None
# 全局快捷键变量，从配置文件加载
hotkey = "ctrl+shift+a"  # 提供一个默认值

def open_settings_window():
    """创建并显示设置窗口，如果它不存在的话。"""
    global settings_window
    if settings_window is None:
        # 创建一个全新的窗口实例，并传入 js_api
        settings_window = webview.create_window(
            "设置", 
            "static/setting.html", 
            width=850, 
            height=600, 
            resizable=False, 
            js_api=api
        )
        # 监听关闭事件，以便我们可以重置变量，允许窗口被再次创建
        def on_settings_close():
            global settings_window
            logging.info("Settings window closed.")
            settings_window = None
        
        settings_window.events.closing += on_settings_close
    else:
        # 如果窗口已存在（可能只是被最小化了），则将其带到前台
        settings_window.show()


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
        pystray.MenuItem('设置', open_settings_window),
        pystray.MenuItem('退出', quit_app)
    )

    # 创建托盘图标
    tray_icon = pystray.Icon("SimpleAI", image, "SimpleAI", menu)
    logging.info("System tray icon is running.")
    # 这会阻塞，直到调用 icon.stop()
    tray_icon.run()


def start_keyboard_listener():
    """启动全局快捷键监听。"""
    global hotkey
    # 从配置中读取快捷键
    # 这确保了即使 change_hotkey 失败，重启后也能加载正确的快捷键
    try:
        settings = api.get_settings()
        hotkey = settings.get('hotkey', 'ctrl+shift+a')
    except Exception:
        pass # 使用默认值

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

    # 启动时检查 API Key，如果为空则自动打开设置窗口
    if not api.settings.get("api_key"):
        logging.warning("API key is missing. Opening settings window automatically.")
        open_settings_window()

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