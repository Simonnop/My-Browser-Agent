# --- 逻辑更新：只捕捉当前聚焦的那一个元素 ---
JS_GET_ONLY_FOCUS = """
() => {
    // 1. 递归查找真正获得焦点的最深层元素 (穿透所有 Shadow DOM)
    const getDeepActiveElement = (root = document) => {
        let el = root.activeElement;
        while (el && el.shadowRoot && el.shadowRoot.activeElement) {
            el = el.shadowRoot.activeElement;
        }
        return el;
    };

    const target = getDeepActiveElement();

    // 如果焦点在 body 或 html 上，说明没有聚焦在具体的输入框
    if (!target || target === document.body || target === document.documentElement) {
        return [];
    }

    // 2. 获取该元素的坐标和属性
    const rect = target.getBoundingClientRect();
    
    // 如果元素太小或不可见，可能不是我们要找的
    if (rect.width <= 0 || rect.height <= 0) return [];

    return [{
        tagName: target.tagName,
        className: target.className,
        text: target.innerText || target.value || "",
        x: rect.left,
        y: rect.top,
        w: rect.width,
        h: rect.height
    }];
}
"""

JS_SET_OF_MARKS = """
() => {
    const isVisible = (el, rect) => {
        const style = window.getComputedStyle(el);
        
        // --- 核心优化：针对 Checkbox/Radio 放宽可见性判定 ---
        const isCheckable = el.tagName === 'INPUT' && ['checkbox', 'radio'].includes(el.type);
        if (isCheckable) {
            // 只要不是 display:none 且有尺寸，即便 opacity 为 0 也保留（兼容美化过的组件）
            return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0;
        }
        
        // 其他元素维持原逻辑
        return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
    };

    const isTopElement = (el, rect) => {
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        if (cx < 0 || cx > window.innerWidth || cy < 0 || cy > window.innerHeight) return false;
        const topEl = document.elementFromPoint(cx, cy);
        if (!topEl) return false;
        return el.contains(topEl) || topEl.contains(el);
    };

    const candidates = [];
    const elements = document.querySelectorAll('*');

    elements.forEach(el => {
        const rect = el.getBoundingClientRect();
        if (el.tagName === 'BODY' || el.tagName === 'HTML') return;

        const style = window.getComputedStyle(el);
        const isPointer = style.cursor === 'pointer';
        const isInputType = ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName);

        if ((isPointer || isInputType) && isVisible(el, rect) && isTopElement(el, rect)) {
            candidates.push({
                tagName: el.tagName,
                type: el.type || '',
                x: rect.left,
                y: rect.top,
                w: rect.width,
                h: rect.height,
                area: rect.width * rect.height
            });
        }
    });

    return candidates.filter((itemB, indexB) => {
        // --- 核心优化：Checkbox 豁免过滤 ---
        // 即使 Checkbox 被包裹在其他可点击元素（如 Label）内部，也强制保留
        if (itemB.tagName === 'INPUT' && ['checkbox', 'radio'].includes(itemB.type)) return true;

        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(itemB.tagName)) return true;

        const isCoveredByOthers = candidates.some((itemA, indexA) => {
            if (indexA === indexB) return false;
            const aCoversB = (
                itemB.x >= itemA.x - 0.5 &&
                itemB.y >= itemA.y - 0.5 &&
                (itemB.x + itemB.w) <= (itemA.x + itemA.w) + 0.5 &&
                (itemB.y + itemB.h) <= (itemA.y + itemA.h) + 0.5
            );
            return aCoversB && (itemA.area > itemB.area);
        });

        return !isCoveredByOthers;
    });
}
"""


# --- 核心 JS：检测可滚动区域 ---
JS_MARK_SCROLLABLE = """
() => {
    const scrollableElements = [];
    const elements = document.querySelectorAll('*');

    elements.forEach(el => {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        
        // 1. 基础过滤：不可见或太小的元素不计入
        if (rect.width < 10 || rect.height < 10) return;
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return;

        // 2. 判定逻辑
        const overflowY = style.overflowY;
        const overflowX = style.overflowX;
        
        const hasScrollStyle = (s) => s === 'auto' || s === 'scroll';
        
        // 检查溢出属性 + 实际内容是否超出容器
        const canScrollY = hasScrollStyle(overflowY) && el.scrollHeight > el.clientHeight + 2;
        const canScrollX = hasScrollStyle(overflowX) && el.scrollWidth > el.clientWidth + 2;

        // 3. 特殊处理：根节点（HTML/BODY）代表整个页面的滚动
        const isRoot = el.tagName === 'HTML' || el.tagName === 'BODY';
        const isPageScroll = isRoot && (document.documentElement.scrollHeight > window.innerHeight);

        if (canScrollY || canScrollX || isPageScroll) {
            // 只保留在视口内的滚动区域
            if (rect.bottom < 0 || rect.top > window.innerHeight || 
                rect.right < 0 || rect.left > window.innerWidth) return;

            scrollableElements.push({
                tagName: el.tagName,
                id: el.id || '',
                className: el.className || '',
                x: rect.left,
                y: rect.top,
                w: rect.width,
                h: rect.height,
                area: rect.width * rect.height,
                type: isPageScroll ? 'page' : (canScrollY ? 'vertical' : 'horizontal')
            });
        }
    });

    // 4. 按面积降序排列：确保小的滚动区域（子元素）在绘制时标签不会被大的（父元素）完全挡住
    return scrollableElements.sort((a, b) => b.area - a.area);
}
"""