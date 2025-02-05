from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from ...services.file_service import FileService
from pathlib import Path
from ...config.settings import Settings

router = APIRouter(prefix="/api/lessons", tags=["lessons"])
settings = Settings()

def get_file_service():
    return FileService(settings.WORDS_FILE)

@router.get("")
async def get_lessons(
    file_service: FileService = Depends(get_file_service)
):
    """获取所有课程信息"""
    lessons = file_service.read_lessons()
    return {
        "success": True,
        "data": lessons
    }

@router.get("/{grade}/{lesson}/words")
async def get_lesson_words(
    grade: str,
    lesson: str,
    file_service: FileService = Depends(get_file_service)
):
    """获取指定课程的单词列表"""
    words = file_service.get_words(grade, lesson)
    if words is None:
        raise HTTPException(status_code=404, detail="课程不存在")
        
    return {
        "success": True,
        "data": {
            "words": words,
            "total": len(words)
        }
    }

@router.post("/{grade}/{lesson}/words")
async def add_lesson_words(
    grade: str,
    lesson: str,
    words: List[str],
    file_service: FileService = Depends(get_file_service)
):
    """添加单词到指定课程"""
    success = file_service.add_words(grade, lesson, words)
    if not success:
        raise HTTPException(status_code=500, detail="添加单词失败")
        
    return {
        "success": True,
        "message": "添加成功"
    } 