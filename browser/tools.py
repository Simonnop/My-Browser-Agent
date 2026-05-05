import colorsys

def get_high_contrast_color(index):
    h = (index * 0.618033988749895) % 1
    r, g, b = colorsys.hls_to_rgb(h, 0.4, 0.8)
    return (int(r * 255), int(g * 255), int(b * 255))

def get_color_by_type(scroll_type):
    """根据滚动类型返回不同颜色"""
    if scroll_type == 'page':
        return (255, 45, 85)    # 红色：全局滚动
    elif scroll_type == 'vertical':
        return (0, 122, 255)   # 蓝色：纵向局部滚动
    else:
        return (52, 199, 89)    # 绿色：横向局部滚动