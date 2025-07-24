window.addEventListener('load', () => {
    const form = document.getElementById('user-area');
    const reset_button = document.getElementById('reset-button');
    const input_txt = document.getElementById('input-txt');
    const send_button = document.getElementById("send-button");
    const change_prompt_button = document.getElementById('change-prompt');
    const prompt_area = document.getElementById('prompt-area');
    const close_prompt_modal_button = document.getElementById('close-prompt-modal');
    const clear_screen_button = document.getElementById('clear-screen'); // 获取新按钮的引用


    // pin_button.addEventListener('click', () => {
    //     // JS现在只管发命令，不管结果，结果由Python通过updatePinButton通知
    //     window.pywebview.api.toggle_pin();
    // });

    input_txt.addEventListener('keydown', (event) => {
        // 检查是否只按下了 Enter 键（没有同时按 Ctrl）
        if (event.key === 'Enter' && event.ctrlKey) {
            // 阻止默认的换行行为
            event.preventDefault();
            // 编程方式触发“发送”按钮的点击，
            send_button.click();
        }
        // 对于 Ctrl + Enter，我们不进行干预，浏览器会执行默认的换行操作
    });

    form.addEventListener('submit', (event) => {
        // 阻止表单的默认提交行为（这会刷新页面，我们不希望）
        event.preventDefault();
        
        const message = input_txt.value.trim();
        if (message) {
            // 将用户自己的消息添加到聊天窗口
            addMessageToChat(message, 'user');
            // 重点：调用 Python 的 process_input 方法
            // window.pywebview.api 是 pywebview 自动注入的对象
            window.pywebview.api.process_input(message);
            // 清空输入框
            input_txt.value = '';
        }
    });
    
    reset_button.addEventListener('click', () => {
        // 1. 找到最后一个 AI 的回答元素
        const chatOutput = document.getElementById('ai-area');
        // 我们选择最后一个同时拥有 'ai-response' 和 'ai' 类名的子元素
        const lastAiMessage = chatOutput.querySelector('.ai-response.ai:last-child');

        // 2. 如果找到了，就从界面上移除它，为新的回答腾出空间
        if (lastAiMessage) {
            lastAiMessage.remove();
        }

        // 3. 调用后端的 regenerate_response 方法
        window.pywebview.api.regenerate_response();
    });
    
    change_prompt_button.addEventListener('click', () => {
        // 1. 先从后端获取并渲染最新的提示词列表
        renderPromptOptions();
        // 2. 然后再显示弹窗
        prompt_area.style.display = 'flex';
    });

    close_prompt_modal_button.addEventListener('click', () => {
        prompt_area.style.display = 'none';
    });


    // 这就是实现点击外部区域关闭的核心逻辑
    window.addEventListener('click', (event) => {
        // event.target 会告诉我们用户实际点击的是哪个元素
        // 如果用户点击的是 prompt_area 本身（也就是遮罩层），而不是其子元素，我们就关闭它
        if (event.target == prompt_area) {
            prompt_area.style.display = "none";
        }
    });

    // 为清屏按钮添加点击事件监听器
    if (clear_screen_button) {
        clear_screen_button.addEventListener('click', () => {
            const chatOutput = document.getElementById('ai-area');
            // 移除所有子元素，即清空聊天记录
            chatOutput.innerHTML = '';
            // 重新添回初始的欢迎消息
            addMessageToChat('你好！有什么可以帮你的吗？', 'ai');
        });
    }

    // 将原本在外部的 prompt 切换事件监听器移到这里
    const prompt_options_container = document.getElementById('prompt-options');
    if (prompt_options_container) {
        prompt_options_container.addEventListener('click', (e) => {
            // 确保点击的是一个 prompt-option 元素
            if (e.target && e.target.classList.contains('prompt-option')) {
                const selected_prompt = e.target.getAttribute('prompt-id');
                // 调用 Python 后端的 set_prompt_profile 方法
                window.pywebview.api.set_prompt_profile(selected_prompt);
                // 选择后自动关闭弹窗
                document.getElementById('prompt-area').style.display = 'none';
            }
        });
    }
});

function addMessageToChat(text, sender) {
    const chatOutput = document.getElementById('ai-area');
    const messageElement = document.createElement('div');
    messageElement.classList.add('ai-response', sender);
    messageElement.innerHTML = marked.parse(text);
    chatOutput.appendChild(messageElement);
    chatOutput.scrollTop = chatOutput.scrollHeight;
}

function renderPromptOptions() {
    const container = document.getElementById('prompt-options');
    container.innerHTML = ''; // 清空旧列表

    window.pywebview.api.get_prompts().then(prompts => {
        for (const id in prompts) {
            const option = document.createElement('div');
            option.className = 'prompt-option';
            option.setAttribute('prompt-id', id);
            option.textContent = prompts[id].name;
            container.appendChild(option);
        }
    });
}

