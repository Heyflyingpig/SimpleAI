window.addEventListener('pywebviewready', () => {
    // pywebview 准备就绪后，立即加载当前设置
    loadCurrentSettings();
});

document.addEventListener('DOMContentLoaded', () => {
    const saveButton = document.getElementById('save-settings-btn');
    const navItems = document.querySelectorAll('.nav-item');
    const hotkeyInput = document.getElementById('hotkey-input');
    const saveHotkeyButton = document.getElementById('save-hotkey-btn');
    const savePromptButton = document.getElementById('save-prompt-btn');
    const clearPromptFormButton = document.getElementById('clear-prompt-form-btn');

    // 为保存按钮添加点击事件
    if (saveButton) {
        saveButton.addEventListener('click', saveSettings);
    }

    // 为保存快捷键按钮添加点击事件
    if (saveHotkeyButton) {
        saveHotkeyButton.addEventListener('click', saveHotkey);
    }

    // 为保存提示词按钮添加点击事件
    if(savePromptButton) {
        savePromptButton.addEventListener('click', savePrompt);
    }

    // 为清空提示词表单按钮添加点击事件
    if(clearPromptFormButton) {
        clearPromptFormButton.addEventListener('click', clearPromptForm);
    }

    // 为快捷键输入框添加键盘事件监听
    if (hotkeyInput) {
        hotkeyInput.addEventListener('keydown', handleHotkeyInput);
    }

    // 为左侧导航项添加点击事件，用于切换页面
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            // 移除所有选项的 active 类
            navItems.forEach(i => i.classList.remove('active'));
            // 为当前点击的选项添加 active 类
            item.classList.add('active');

            // 切换右侧内容页面
            const targetId = item.getAttribute('data-target');
            document.querySelectorAll('.page').forEach(page => {
                page.classList.remove('active');
            });
            document.getElementById(targetId).classList.add('active');
        });
    });
});

function loadCurrentSettings() {
    // 调用 Python 的 get_settings 方法
    window.pywebview.api.get_settings().then(settings => {
        if (settings) {
            document.getElementById('model-name').value = settings.model_name || '';
            document.getElementById('api-key').value = settings.api_key || '';
            document.getElementById('base-url').value = settings.base_url || '';
            // 加载并显示当前快捷键
            document.getElementById('hotkey-input').value = settings.hotkey || 'ctrl+shift+a';
        }
    });
    // 加载提示词
    loadPrompts();
}

function saveSettings() {
    const modelName = document.getElementById('model-name').value;
    const apiKey = document.getElementById('api-key').value;
    const baseUrl = document.getElementById('base-url').value;

    const settingsData = {
        model_name: modelName,
        api_key: apiKey,
        base_url: baseUrl,
        // 保存时，把当前的快捷键也一并保存，避免被覆盖
        hotkey: document.getElementById('hotkey-input').value
    };

    // 调用 Python 的 save_settings 方法
    window.pywebview.api.save_settings(settingsData).then(() => {
        const statusElement = document.getElementById('save-status');
        statusElement.textContent = '设置已保存成功！';
        statusElement.style.color = 'green';

        // 2秒后清除提示信息
        setTimeout(() => {
            statusElement.textContent = '';
        }, 2000);
    });
}



let prompts = {}; // 用于在本地缓存提示词

function loadPrompts() {
    window.pywebview.api.get_prompts().then(loadedPrompts => {
        prompts = loadedPrompts;
        renderPromptList();
    });
}

function renderPromptList() {
    const promptList = document.getElementById('prompt-list');
    promptList.innerHTML = ''; // 清空现有列表

    for (const id in prompts) {
        const item = document.createElement('li');
        item.className = 'prompt-list-item';
        item.dataset.id = id;

        const nameSpan = document.createElement('span');
        nameSpan.textContent = prompts[id].name;
        item.appendChild(nameSpan);

        // 'default' 提示词不能被删除
        if (id !== 'default') {
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'delete-btn';
            deleteBtn.textContent = '删除';
            deleteBtn.onclick = (e) => {
                e.stopPropagation(); // 阻止事件冒泡到父元素 li 的点击事件
                deletePrompt(id);
            };
            item.appendChild(deleteBtn);
        }

        item.onclick = () => {
            selectPrompt(id);
        };

        promptList.appendChild(item);
    }
}

function selectPrompt(id) {
    // 高亮显示选中的项
    document.querySelectorAll('.prompt-list-item').forEach(item => {
        item.classList.toggle('selected', item.dataset.id === id);
    });

    const promptData = prompts[id];
    document.getElementById('prompt-id').value = id;
    document.getElementById('prompt-name').value = promptData.name;
    document.getElementById('prompt-text').value = promptData.prompt;
    
    // 'default' 提示词的名称和ID不能被修改
    const isDefault = id === 'default';
    document.getElementById('prompt-name').disabled = isDefault;

}

function clearPromptForm() {
    document.getElementById('prompt-id').value = '';
    document.getElementById('prompt-name').value = '';
    document.getElementById('prompt-text').value = '';
    document.getElementById('prompt-name').disabled = false;
    // 清除高亮
    document.querySelectorAll('.prompt-list-item').forEach(item => {
        item.classList.remove('selected');
    });
}

function savePrompt() {
    const id = document.getElementById('prompt-id').value;
    const name = document.getElementById('prompt-name').value;
    const text = document.getElementById('prompt-text').value;

    if (!name || !text) {
        alert('提示词名称和内容不能为空！');
        return;
    }

    window.pywebview.api.save_prompt(id, name, text).then(response => {
        if (response.success) {
            prompts = response.prompts;
            renderPromptList();
            // 如果是新建，则清空表单；如果是编辑，则保持选中
            if (!id) {
                clearPromptForm();
            }
            alert('提示词已保存！');
        } else {
            alert('保存失败: ' + response.error);
        }
    });
}

function deletePrompt(id) {
    if (confirm(`确定要删除提示词 "${prompts[id].name}" 吗？`)) {
        window.pywebview.api.delete_prompt(id).then(response => {
            if (response.success) {
                prompts = response.prompts;
                renderPromptList();
                clearPromptForm(); // 删除后清空表单
                alert('提示词已删除！');
            } else {
                alert('删除失败: ' + response.error);
            }
        });
    }
}


let currentHotkey = ''; // 用于临时存储用户按下的快捷键

function handleHotkeyInput(event) {
    // 阻止默认行为，比如输入字符
    event.preventDefault();

    const parts = [];
    if (event.ctrlKey) parts.push('ctrl');
    if (event.altKey) parts.push('alt');
    if (event.shiftKey) parts.push('shift');

    // 只处理字母和数字键作为主键
    const key = event.key.toLowerCase();
    if (key.match(/^[a-z0-9]$/)) {
        parts.push(key);
    } else if (!['control', 'alt', 'shift'].includes(key)) {
        // 如果按下的不是修饰键或字母数字，提示不合法
        this.value = '';
        this.placeholder = '无效按键，请重试';
        return;
    }
    
    // 至少需要一个修饰键和一个主键
    if (parts.length > 1 && parts.some(p => p.length === 1)) {
        currentHotkey = parts.join('+');
        this.value = currentHotkey;
    } else {
        // 如果只按了修饰键，则清空
        this.value = parts.join('+') + (parts.length > 0 ? '+' : '');
        currentHotkey = '';
    }
}

function saveHotkey() {
    if (currentHotkey) {
        // 调用 Python 的 change_hotkey 方法
        window.pywebview.api.change_hotkey(currentHotkey).then(() => {
            const statusElement = document.getElementById('hotkey-save-status');
            statusElement.textContent = '快捷键保存成功！';
            statusElement.style.color = 'green';

            setTimeout(() => {
                statusElement.textContent = '';
            }, 2000);
        });
    } else {
        const statusElement = document.getElementById('hotkey-save-status');
        statusElement.textContent = '请先设置一个有效的快捷键。';
        statusElement.style.color = 'red';
        setTimeout(() => {
            statusElement.textContent = '';
        }, 2000);
    }
} 