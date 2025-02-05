# Web Dictation App

一个支持中英文的在线听写系统，提供可配置的TTS服务，支持通过Web浏览器访问。

** 全程使用cursor开发，几乎没有自己手动改代码文件。**

## 问题
- 使用edge tts时，时延较大，需要优化；目前是做了缓存。
- 使用web speech api时，需要浏览器支持，目前移动端浏览器和微信暂时不支持


## 功能特点

- 支持中英文听写
- 多种TTS引擎选择
  - Edge TTS（支持多种语音）
  - Web Speech API（使用浏览器内置语音）
- 丰富的语音配置
  - 可调节语速（0.5-2.0倍速）
  - 多种音色选择（中英文男声/女声）
  - 自定义重复次数和间隔时间
- 灵活的播放控制
  - 顺序/随机播放
  - 单词重复播放
  - 自定义重复间隔
- 缓存机制
  - 自动缓存音频文件
  - 显示缓存进度
  - 断点续传支持
- 批量处理
  - 支持生成完整的听写音频文件
  - 自动添加提示音
  - 支持导出MP3格式
- 数据管理
  - Excel文件数据管理
  - 支持按年级和课时组织单词
  - 支持动态添加和修改
- 系统特性
  - 并发控制和会话管理
  - 优雅的错误处理
  - 实时进度显示
  - 响应式界面设计

## 系统要求

- Python >= 3.8
- FFmpeg（用于音频处理）
- 操作系统：Windows/Linux/macOS
- 现代浏览器（支持Web Speech API）

## 快速开始

1. 克隆项目
```bash
git clone https://github.com/yourusername/web-dictation-app.git
cd web-dictation-app
```

2. 创建虚拟环境
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 安装 FFmpeg
- Windows: 从 [FFmpeg官网](https://ffmpeg.org/download.html) 下载并添加到系统PATH
- Linux: `sudo apt install ffmpeg` (Ubuntu/Debian)
- macOS: `brew install ffmpeg` (使用Homebrew)

5. 配置环境变量
创建 `.env` 文件在项目根目录：
```env
PORT=8000
MAX_CONCURRENCY=3
TIMEOUT=300
CORS_ORIGINS=["*"]
WORDS_FILE=data/words.xlsx
```

6. 准备词语数据
在 `data/words.xlsx` 文件中按以下格式组织数据：
```
年级        课时     词语
二年级语文上册  第1课    看见,哪里,那边,春天,夏天,秋天,冬天,美丽
```

7. 运行应用
```bash
# 开发环境
uvicorn src.main:app --reload --port 8000

# 生产环境
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

8. 访问应用
- 前端界面：http://localhost:8000
- API文档：http://localhost:8000/docs

## 目录结构
```
/
├── frontend/          # 前端文件
│   ├── index.html    # 主页面
│   ├── js/          # JavaScript文件
│   ├── css/         # 样式文件
│   └── img/         # 图片资源
├── src/              # 后端源码
│   ├── api/         # API接口
│   ├── services/    # 业务服务
│   ├── config/      # 配置文件
│   └── middleware/  # 中间件
├── data/             # 数据文件
│   └── words.xlsx   # 词语数据
├── cache/            # 缓存目录
│   └── tts/         # TTS音频缓存
├── MP3/              # 生成的MP3文件
└── requirements.txt  # Python依赖
```

## API文档

### 课程管理
- `GET /api/lessons` - 获取所有课程信息
- `GET /api/lessons/{grade}/{lesson}/words` - 获取指定课程的单词列表

### TTS服务
- `POST /api/tts` - 生成单个词语的语音
- `POST /api/tts/batch` - 生成完整的听写音频文件
- `GET /api/tts/voices` - 获取可用的语音列表
- `GET /api/tts/config` - 获取TTS配置
- `POST /api/tts/check-cache` - 检查并准备缓存

### 系统状态
- `GET /api/status` - 获取系统并发状态

## 开发说明

### 代码规范
1. 遵循 PEP 8 编码规范
2. 使用类型注解
3. 编写完整的文档字符串
4. 实现错误处理和日志记录

### 缓存机制
- TTS生成的音频文件会自动缓存
- 缓存目录：`cache/tts/`
- 缓存文件使用MD5命名
- 支持自动清理和更新

### 音频处理
- 使用 FFmpeg 进行音频处理
- 支持音频合并和格式转换
- 自动添加提示音和间隔

## 安全说明
- 限制并发请求数
- 实现会话控制
- 文件上传限制
- 路径遍历防护

## 许可证

MIT License 