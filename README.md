# Web Dictation App

一个支持中英文的在线听写系统，提供可配置的TTS服务，支持通过Web浏览器和微信内置浏览器访问。

## 功能特点

- 支持中英文听写
- 多种TTS引擎选择（Edge TTS、Web Speech API）
- 可配置的语音参数（语速、音色）
- 灵活的播放控制（顺序/随机、重复次数、间隔时间）
- 并发控制和会话管理
- 本地CSV文件数据管理

## 系统要求

- Python >= 3.8
- 操作系统：Windows/Linux/macOS

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

4. 运行应用
```bash
# 开发环境
uvicorn src.main:app --reload --port 8000

# 生产环境
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

5. 访问应用
- API文档：http://localhost:8000/docs
- 前端界面：http://localhost:8000

## 配置说明

### 环境变量
创建 `.env` 文件在项目根目录：

```env
PORT=8000
MAX_CONCURRENCY=3
TIMEOUT=300
CORS_ORIGINS=["*"]
CSV_PATH=data/words.csv
```

### 词语数据
词语数据存储在 `data/words.csv` 文件中，格式如下：
```csv
grade,lesson,words
二年级语文上册,第1课,看见,哪里,那边,春天,夏天,秋天,冬天,美丽
```

## API文档

### 1. 课程管理
- `GET /api/lessons` - 获取所有课程信息
- `GET /api/lessons/{grade}/{lesson}/words` - 获取指定课程的单词列表
- `POST /api/lessons/{grade}/{lesson}/words` - 添加单词到指定课程

### 2. TTS服务
- `POST /api/tts` - 生成语音
- `GET /api/tts/voices` - 获取可用的语音列表

### 3. 系统状态
- `GET /api/status` - 获取系统并发状态

## 开发说明

### 项目结构
```
/src
├── config/         # 配置文件
├── services/       # 业务服务
├── api/           # API路由
├── middleware/    # 中间件
└── utils/         # 工具函数
```

### 开发规范
1. 代码风格遵循PEP 8
2. 使用类型注解
3. 编写完整的文档字符串
4. 异常处理和日志记录

## 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交代码
4. 创建 Pull Request

## 许可证

MIT License 