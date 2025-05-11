/**
 * ExcelLLM - Excel数据AI批处理工具
 * 公共JavaScript函数库
 */

// 在页面加载完成后执行
$(document).ready(function() {
    // 初始化工具提示
    initTooltips();
    
    // 监听表单提交，防止意外刷新
    initFormProtection();
});

/**
 * 初始化Bootstrap工具提示
 */
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}


/**
 * 初始化表单保护，防止意外刷新
 */
function initFormProtection() {
    // 找到所有重要表单
    const forms = document.querySelectorAll('form.protect-form');
    
    forms.forEach(form => {
        let formChanged = false;
        
        // 监听表单变化
        form.addEventListener('input', function() {
            formChanged = true;
        });
        
        // 监听表单提交
        form.addEventListener('submit', function() {
            formChanged = false;
        });
        
        // 监听页面关闭
        window.addEventListener('beforeunload', function(e) {
            if (formChanged) {
                const message = '您有未保存的更改，确定要离开吗？';
                e.returnValue = message;
                return message;
            }
        });
    });
}

/**
 * 格式化日期时间
 * @param {string|Date} datetime - 日期时间对象或字符串
 * @param {string} format - 格式化模式 (可选)
 * @returns {string} 格式化后的日期时间字符串
 */
function formatDateTime(datetime, format = 'YYYY-MM-DD HH:mm:ss') {
    if (!datetime) return '';
    
    const dt = typeof datetime === 'string' ? new Date(datetime) : datetime;
    if (isNaN(dt.getTime())) return datetime; // 如果无效日期则返回原始值
    
    const year = dt.getFullYear();
    const month = String(dt.getMonth() + 1).padStart(2, '0');
    const day = String(dt.getDate()).padStart(2, '0');
    const hours = String(dt.getHours()).padStart(2, '0');
    const minutes = String(dt.getMinutes()).padStart(2, '0');
    const seconds = String(dt.getSeconds()).padStart(2, '0');
    
    return format
        .replace('YYYY', year)
        .replace('MM', month)
        .replace('DD', day)
        .replace('HH', hours)
        .replace('mm', minutes)
        .replace('ss', seconds);
}

/**
 * 格式化文件大小
 * @param {number} bytes - 字节数
 * @param {number} decimals - 小数位数 (可选)
 * @returns {string} 格式化后的文件大小
 */
function formatFileSize(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * 显示加载遮罩
 * @param {string} message - 加载提示消息 (可选)
 * @param {string} target - 目标元素选择器 (可选)
 */
function showLoading(message = '正在加载...', target = 'body') {
    // 创建加载遮罩
    const loadingEl = document.createElement('div');
    loadingEl.className = 'loading-overlay';
    loadingEl.innerHTML = `
        <div class="loading-spinner">
            <div class="spinner-border text-primary" role="status"></div>
            <div class="mt-2">${message}</div>
        </div>
    `;
    
    // 添加样式
    loadingEl.style.position = target === 'body' ? 'fixed' : 'absolute';
    loadingEl.style.top = '0';
    loadingEl.style.left = '0';
    loadingEl.style.width = '100%';
    loadingEl.style.height = '100%';
    loadingEl.style.backgroundColor = 'rgba(255, 255, 255, 0.7)';
    loadingEl.style.display = 'flex';
    loadingEl.style.justifyContent = 'center';
    loadingEl.style.alignItems = 'center';
    loadingEl.style.zIndex = '9999';
    
    // 将遮罩添加到目标元素
    document.querySelector(target).appendChild(loadingEl);
    
    return loadingEl;
}

/**
 * 隐藏加载遮罩
 * @param {Element} loadingElement - 加载遮罩元素
 */
function hideLoading(loadingElement) {
    if (loadingElement && loadingElement.parentNode) {
        loadingElement.parentNode.removeChild(loadingElement);
    } else {
        // 如果没有传入特定元素，则移除所有加载遮罩
        const loadings = document.querySelectorAll('.loading-overlay');
        loadings.forEach(el => el.parentNode.removeChild(el));
    }
}

/**
 * 显示通知提示
 * @param {string} message - 通知消息
 * @param {string} type - 通知类型 (success, info, warning, error)
 * @param {number} duration - 持续时间 (毫秒)
 */
function showNotification(message, type = 'info', duration = 3000) {
    // 使用SweetAlert2显示通知
    Swal.fire({
        title: message,
        icon: type,
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: duration,
        timerProgressBar: true
    });
}

/**
 * 复制文本到剪贴板
 * @param {string} text - 要复制的文本
 * @param {Function} callback - 复制成功后的回调函数 (可选)
 */
function copyToClipboard(text, callback) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text)
            .then(() => {
                if (callback) callback(true);
                else showNotification('复制成功', 'success');
            })
            .catch(err => {
                console.error('复制失败:', err);
                if (callback) callback(false, err);
                else showNotification('复制失败', 'error');
            });
    } else {
        // 兼容旧版浏览器
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            const successful = document.execCommand('copy');
            document.body.removeChild(textArea);
            if (successful) {
                if (callback) callback(true);
                else showNotification('复制成功', 'success');
            } else {
                if (callback) callback(false);
                else showNotification('复制失败', 'error');
            }
        } catch (err) {
            document.body.removeChild(textArea);
            console.error('复制失败:', err);
            if (callback) callback(false, err);
            else showNotification('复制失败', 'error');
        }
    }
}

/**
 * 格式化时间间隔为人类可读格式
 * @param {number} seconds - 秒数
 * @returns {string} 格式化后的时间
 */
function formatTimeInterval(seconds) {
    if (seconds < 60) {
        return `${Math.round(seconds)}秒`;
    } else if (seconds < 3600) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.round(seconds % 60);
        return `${minutes}分钟${remainingSeconds > 0 ? ' ' + remainingSeconds + '秒' : ''}`;
    } else {
        const hours = Math.floor(seconds / 3600);
        const remainingMinutes = Math.floor((seconds % 3600) / 60);
        return `${hours}小时${remainingMinutes > 0 ? ' ' + remainingMinutes + '分钟' : ''}`;
    }
}

/**
 * 防抖函数
 * @param {Function} func - 要执行的函数
 * @param {number} wait - 等待时间 (毫秒)
 * @returns {Function} 防抖处理后的函数
 */
function debounce(func, wait) {
    let timeout;
    return function() {
        const context = this;
        const args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            func.apply(context, args);
        }, wait);
    };
}

/**
 * 节流函数
 * @param {Function} func - 要执行的函数
 * @param {number} limit - 时间间隔 (毫秒)
 * @returns {Function} 节流处理后的函数
 */
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const context = this;
        const args = arguments;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}