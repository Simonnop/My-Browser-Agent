import os
import shutil

class SaveTool:
    """
    文件保存工具
    """
    @staticmethod
    def prepare_dir(dir_path: str, clear: bool = True):
        """
        准备目录，可选清空
        """
        if clear and os.path.exists(dir_path):
            shutil.rmtree(dir_path)
        
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    @staticmethod
    def save_image(data: bytes, path: str):
        """
        保存图片数据
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    @staticmethod
    def save_text(content: str, path: str):
        """
        保存文本数据
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
