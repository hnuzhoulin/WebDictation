import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
import time

class FileService:
    def __init__(self, excel_path: Path):
        """
        初始化文件服务
        
        Args:
            excel_path: Excel文件路径
        """
        self.excel_path = excel_path
        if not self.excel_path.exists():
            raise FileNotFoundError(f"词语文件不存在: {self.excel_path}")
        
        self._df_cache = None  # DataFrame 缓存
        self._df_cache_time = 0  # 缓存时间
        self._df_cache_ttl = 60  # 缓存有效期（1分钟）
        self._lessons_cache = None  # 课程列表缓存
        self._lessons_cache_time = 0  # 课程列表缓存时间
        
    def _read_excel(self) -> pd.DataFrame:
        """读取 Excel 文件并缓存"""
        current_time = time.time()
        
        # 检查文件是否被修改
        file_mtime = self.excel_path.stat().st_mtime
        
        # 如果缓存有效且文件未修改，返回缓存的数据
        if (self._df_cache is not None and 
            current_time - self._df_cache_time < self._df_cache_ttl and
            file_mtime <= self._df_cache_time):
            print("使用缓存的 DataFrame")
            return self._df_cache
            
        # 读取新数据
        print(f"正在读取Excel文件: {self.excel_path}")
        start_time = time.time()
        df = pd.read_excel(self.excel_path)
        
        # 更新缓存
        self._df_cache = df
        self._df_cache_time = current_time
        
        print(f"Excel文件读取完成，耗时: {(time.time() - start_time):.2f}秒")
        return df
                
    def read_lessons(self) -> List[Dict]:
        """
        读取所有课程信息
        
        Returns:
            课程列表，每个课程包含年级、课时和单词数量
        """
        try:
            current_time = time.time()
            
            # 检查缓存是否有效
            if (self._lessons_cache is not None and 
                current_time - self._lessons_cache_time < self._df_cache_ttl):
                print("使用缓存的课程列表")
                return self._lessons_cache
                
            print("开始处理课程数据...")
            start_time = time.time()
            
            df = self._read_excel()
            lessons = []
            
            for (grade, lesson), group in df.groupby(['年级', '课时']):
                # 获取该课程的所有单词
                words = []
                for word_list in group['词语'].dropna():  # 忽略空值
                    if isinstance(word_list, str):  # 确保是字符串
                        words.extend([w.strip() for w in word_list.split(',')])
                
                lesson_info = {
                    'grade': str(grade).strip(),  # 确保是字符串并去除空白
                    'lesson': str(lesson).strip(),  # 确保是字符串并去除空白
                    'wordCount': len(words)
                }
                lessons.append(lesson_info)
                
            # 更新缓存
            self._lessons_cache = lessons
            self._lessons_cache_time = current_time
            
            print(f"课程数据处理完成，总共 {len(lessons)} 个课程，耗时: {(time.time() - start_time):.2f}秒")
            return lessons
            
        except Exception as e:
            print(f"读取课程信息失败: {str(e)}")
            import traceback
            traceback.print_exc()
            # 如果有缓存，在出错时返回缓存的数据
            if self._lessons_cache is not None:
                print("使用缓存的课程列表（出错回退）")
                return self._lessons_cache
            return []
            
    def get_words(self, grade: str, lesson: str) -> Optional[List[str]]:
        """
        获取指定课程的单词列表
        
        Args:
            grade: 年级
            lesson: 课时
            
        Returns:
            单词列表
        """
        try:
            df = self._read_excel()  # 使用缓存的 DataFrame
            
            # 确保进行比较的值类型一致
            df['年级'] = df['年级'].astype(str).str.strip()
            df['课时'] = df['课时'].astype(str).str.strip()
            grade = str(grade).strip()
            lesson = str(lesson).strip()
            
            filtered = df[(df['年级'] == grade) & (df['课时'] == lesson)]
            
            if filtered.empty:
                print(f"未找到课程: {grade} - {lesson}")
                return None
                
            # 合并所有单词并去重
            words = set()
            for word_list in filtered['词语'].dropna():
                if isinstance(word_list, str):
                    words.update([w.strip() for w in word_list.split(',')])
                
            result = sorted(list(words))
            print(f"找到单词: {result}")
            return result
            
        except Exception as e:
            print(f"获取单词列表失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
            
    def add_words(self, grade: str, lesson: str, words: List[str]) -> bool:
        """
        添加单词到指定课程
        
        Args:
            grade: 年级
            lesson: 课时
            words: 单词列表
            
        Returns:
            是否添加成功
        """
        try:
            df = pd.read_excel(self.excel_path)
            # 确保进行比较的值类型一致
            df['年级'] = df['年级'].astype(str).str.strip()
            df['课时'] = df['课时'].astype(str).str.strip()
            grade = str(grade).strip()
            lesson = str(lesson).strip()
            
            # 检查是否已存在相同的课程
            mask = (df['年级'] == grade) & (df['课时'] == lesson)
            if mask.any():
                # 更新现有记录
                df.loc[mask, '词语'] = ','.join(words)
            else:
                # 添加新记录
                new_row = pd.DataFrame({
                    '年级': [grade],
                    '课时': [lesson],
                    '词语': [','.join(words)]
                })
                df = pd.concat([df, new_row], ignore_index=True)
                
            # 保存到文件
            with pd.ExcelWriter(self.excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            return True
            
        except Exception as e:
            print(f"添加单词失败: {str(e)}")
            import traceback
            traceback.print_exc()  # 打印详细错误信息
            return False 