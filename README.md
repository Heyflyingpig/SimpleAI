# SimpleAI

这是一个基于 `pywebview` 和 `langchain` 构建的极简跨平台桌面AI应用,目的是用户可以在桌面快速利用快捷键调出桌面进行对话。本应用预设了多个专业prompt，极度提高用户的对话体验，为了将提供自定义prompt等功能


## 🚀 功能特性
- **跨平台桌面应用**: 得益于 `pywebview`，本项目可以轻松打包成 Windows, macOS, 和 Linux 上的原生应用，且响应快速，不占用后台
- **实时AI聊天**: 与配置好的大语言模型进行流畅的对话。
- **可切换的AI角色**: 内置多种提示词（Prompt），可以随时切换AI的“人设”，例如“代码专家”、“翻译专家”等。
- **持久化聊天记录**: 对话历史会自动保存在本地的 `chat_history.db` (SQLite) 文件中，每个AI角色拥有独立的对话历史。

## 🛠️ 技术栈

- **前端**:
    - `HTML`: 页面结构
    - `CSS`: 页面样式
    - `JavaScript`: 交互逻辑
- **后端**:
    - `Python`: 主要的后端逻辑语言。
    - `pywebview`: 核心库，用于将Web内容包装成桌面应用，并建立Python与JavaScript之间的双向通信。
    - `langchain`: 强大的语言模型框架，用于构建、管理和调用AI模型。
        - `ChatOpenAI`: 对接与OpenAI API兼容的语言模型。
        - `SQLChatMessageHistory`: 用于将聊天记录保存到SQLite数据库。
- **数据库**:
    - `SQLite`: 轻量级的本地数据库，用于存储聊天历史。

## 🏃 如何运行

1.  **克隆项目**
    ```bash
    git clone <your-repository-url>
    cd SimpleAI
    ```

2.  **安装依赖**
    项目依赖于一些Python库，你可以通过 `pip` 来安装它们：
    ```bash
    pip install -r requirements.txt
    ```

3.  **配置密钥**
    为了让应用能够连接到大语言模型，你需要提供API密钥等信息。

    a. 在项目的根目录下，创建一个名为 `secrets.json` 的文件。

    b. 将以下内容复制到 `secrets.json` 文件中，并填入你自己的信息：
    ```json
    {
        "model_name": "your-model-name",
        "api_key": "your-api-key",
        "base_url": "your-api-base-url"
    }
    ```
    - `model_name`: 你希望使用的模型名称，例如 `gpt-4` 或其他兼容模型。
    - `api_key`: 你的API密钥。
    - `base_url`: API的访问地址。

4.  **启动应用**
    一切准备就绪后，运行 `main.py` 即可启动应用：
    ```bash
    python main.py
    ```

## 📁 文件结构

```
SimpleAI/
│
├── static/                   # 存放所有前端静态资源
│   ├── CSS/
│   │   └── style.css         # 全局样式表
│   ├── JS/
│   │   ├── script.js         # 前端主要交互逻辑
│   │   └── marked.min.js     # Markdown渲染库
│   └── index.html            # 应用主页面
│
├── main.py                   # 应用主程序入口和后端逻辑
├── requirements.txt          # Python 依赖列表
├── secrets.json              # (需手动创建) 存储API密钥和模型信息
├── chat_history.db           # (自动生成) SQLite数据库文件
└── README.md                 # 项目说明文件
``` 