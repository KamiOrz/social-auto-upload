import os
import re
from pathlib import Path
import openai
from typing import List, Dict
import yaml
from datetime import datetime
import logging

class VideoPreprocessor:
    def __init__(self, config_path: str = "config.yml"):
        # 加载配置文件
        self.config = self._load_config(config_path)
        # 设置OpenAI API配置
        openai.api_key = self.config['openai_api_key']
        if 'openai_api_base' in self.config:
            openai.api_base = self.config['openai_api_base']
        # 设置日志
        self._setup_logging()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('video_processor.log'),
                logging.StreamHandler()
            ]
        )

    def _load_config(self, config_path: str) -> Dict:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _translate_text(self, text: str) -> str:
        """使用GPT-4调用API将英文翻译为中文"""
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """
```xml
<instruction>
作为一个翻译助手，你的任务是将英文翻译成中文。
请按照以下步骤完成任务：
1.将英文翻译成合适的中文
2.只输出翻译后的内容
</instruction>
<example>
输入：Rock Pop Backing Track F Major 70 BPM
输出：摇滚流行伴奏曲 F大调 70 BPM
</example>
                     """},
                    {"role": "user", "content": f"{text}"}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"翻译出错: {e}")
            return text

    def _get_video_description(self, video_name: str) -> str:
        """使用GPT-4生成视频描述和话题"""
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """
```xml
<instruction>
作为一个视频介绍撰写助手，你的任务是根据视频名称编写简短的介绍。
请按照以下步骤完成任务：
1.根据视频名称编写简短的介绍
2.根据视频名称编写合适的话题关键词
3.不要输出其他无关的任何内容
</instruction>
<example>
输入：摇滚流行伴奏曲 F大调 70 BPM
输出：摇滚流行伴奏曲 F大调 70 BPM
#电吉他即兴伴奏 #电吉他伴奏 #摇滚流行伴奏 #F大调伴奏
</example>
                     """},
                    {"role": "user", "content": f"{video_name}"}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"生成描述出错: {e}")
            return f"无法生成描述: {video_name}"

    def _clean_filename(self, filename: str) -> str:
        """清理文件名"""
        name = filename
        
        # 移除配置中指定的字符串
        for pattern in self.config['remove_patterns']:
            if '*' in pattern:
                # 将通配符模式转换为正则表达式
                # 例如 [*] 转换为 \[.*?\]
                regex_pattern = pattern.replace('*', '.*?')
                regex_pattern = re.escape(regex_pattern).replace(r'\.\*\?', '.*?')
                name = re.sub(regex_pattern, '', name)
            else:
                # 对于普通字符串，直接替换
                name = name.replace(pattern, '')

        # 如果配置了翻译
        if self.config.get('translate_to_chinese', False):
            name = self._translate_text(name)

        # 移除特殊字符
        name = re.sub(r'[^\w\s\-\.]', '', name)
        
        # 限制文件名长度
        max_length = self.config.get('max_filename_length', 100)
        if len(name) > max_length:
            name = name[:max_length]

        return name.strip()

    def process_directory(self):
        """处理指定目录中的所有视频文件"""
        video_dir = Path(self.config['video_directory'])
        
        if not video_dir.exists():
            logging.error(f"目录不存在: {video_dir}")
            return

        for video_file in video_dir.glob("*.mp4"):
            try:
                # 获取原始文件名（不含扩展名）
                original_name = video_file.stem
                
                # 清理并格式化文件名
                new_name = self._clean_filename(original_name)
                
                # 构建新的文件路径
                new_video_path = video_file.parent / f"{new_name}.mp4"
                
                # 重命名视频文件
                if video_file != new_video_path:
                    video_file.rename(new_video_path)
                    logging.info(f"重命名文件: {video_file} -> {new_video_path}")

                # 生成描述文件
                description = self._get_video_description(new_name)
                txt_path = video_file.parent / f"{new_name}.txt"
                
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(description)
                
                logging.info(f"生成描述文件: {txt_path}")

            except Exception as e:
                logging.error(f"处理文件 {video_file} 时出错: {e}")

if __name__ == "__main__":
    processor = VideoPreprocessor()
    processor.process_directory() 
