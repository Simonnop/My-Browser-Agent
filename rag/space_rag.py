import math
from typing import List, Dict, Any

class SpaceRAG:
    """
    空间路检索: 根据坐标检索范围内的节点
    """
    def __init__(self, space_table: List[Dict[str, Any]]):
        self.space_table = space_table

    def search(self, focus_point: List[float], viewport_size: Dict[str, int], radius_percent: float = 5.0) -> List[str]:
        """
        查找中心点在视觉聚焦半径区域内的所有节点
        聚焦半径定义为: focus_point 为中心，宽/高为 p% * viewport_width/height 的矩形
        """
        if not focus_point or not self.space_table or not viewport_size:
            return []

        # 计算矩形范围
        p = radius_percent / 100.0
        width_delta = viewport_size['width'] * p
        height_delta = viewport_size['height'] * p

        min_x = focus_point[0] - width_delta / 2
        max_x = focus_point[0] + width_delta / 2
        min_y = focus_point[1] - height_delta / 2
        max_y = focus_point[1] + height_delta / 2

        hit_ids = []
        for entry in self.space_table:
            cx, cy = entry['center']
            # 基础范围核验
            if min_x <= cx <= max_x and min_y <= cy <= max_y:
                # 二次核验：必须在当前视口范围内，且未被遮挡 (is_occluded 为 False)
                if 0 <= cx <= viewport_size['width'] and 0 <= cy <= viewport_size['height']:
                    if not entry.get('is_occluded', False):
                        hit_ids.append(entry['id'])

        # 如果范围内没有任何节点，则回退到寻找最近的一个节点
        if not hit_ids:
            distances = []
            for entry in self.space_table:
                cx, cy = entry['center']
                dist = math.sqrt((cx - focus_point[0])**2 + (cy - focus_point[1])**2)
                distances.append((dist, entry['id']))
            
            if distances:
                distances.sort(key=lambda x: x[0])
                hit_ids = [distances[0][1]]

        return hit_ids
