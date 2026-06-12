# 智能校园知识服务平台

基于 **CrewAI 多智能体协作框架** 的智慧校园知识服务系统，集成多模型 AI 对话、知识库管理、向量检索等功能，为师生提供一站式的智能校园服务。

## 技术架构

| 层级 | 技术栈 |
|------|--------|
| 后端框架 | FastAPI (Python 3.10+) |
| 多智能体 | CrewAI + LangChain |
| 大模型 | OpenAI / 通义千问 / DeepSeek |
| 向量数据库 | FAISS + Chroma |
| 关系数据库 | PostgreSQL |
| 缓存 | Redis |
| 前端 | React + Nginx (Docker 部署) |
| 认证 | JWT (bcrypt + HS256) |

## 功能特性

### 智能体服务
- **学术助手 (Academic Agent)** — 课程查询、成绩查询、选课建议
- **生活服务 (Life Service Agent)** — 食堂、图书馆、校园活动信息
- **导航助手 (Navigation Agent)** — 校园路径指引
- **管理助手 (Admin Agent)** — 系统管理、数据导出
- **质量监控 (Quality Agent)** — 回答质量评估、反馈收集

### 系统功能
- 多角色用户系统（学生 / 教师 / 管理员）
- 知识库管理与文档检索
- 全文搜索
- 对话记录管理与导出
- 用户反馈与评分
- 系统监控与健康检查

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Redis 6+

### 1. 克隆项目

```bash
git clone https://github.com/tao0012/intelligent-campus-platform.git
cd intelligent-campus-platform
```

### 2. 后端配置

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入数据库地址、API Key 等信息

# 初始化数据库
python scripts/init_demo_users.py
```

### 3. 启动后端

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API 文档自动生成，访问 http://localhost:8000/api/v1/docs

### 4. 前端配置

```bash
cd frontend

# 安装依赖
npm install

# 配置环境变量
cp .env.example .env

# 启动开发服务器
npm start
```

### Docker 部署

```bash
# 后端
cd backend
docker build -t campus-backend .
docker run -d -p 8000:8000 --env-file .env campus-backend

# 前端
cd frontend
docker build -t campus-frontend .
docker run -d -p 80:80 campus-frontend
```

## API 接口概览

| 模块 | 路由 | 说明 |
|------|------|------|
| 认证 | `/api/v1/auth` | 登录、注册、密码修改 |
| 对话 | `/api/v1/chat` | AI 对话服务 |
| 智能体 | `/api/v1/agents` | 智能体管理与调用 |
| 知识库 | `/api/v1/knowledge` | 知识库查询 |
| 知识管理 | `/api/v1/knowledge-management` | 知识库后台管理 |
| 搜索 | `/api/v1/search` | 全文搜索 |
| 管理 | `/api/v1/admin` | 后台管理 |
| 反馈 | `/api/v1/feedback` | 用户反馈 |
| 导出 | `/api/v1/export` | 数据导出 |
| 监控 | `/api/v1/monitoring` | 系统监控 |

完整文档见 http://localhost:8000/api/v1/docs

## 演示账户

| 角色 | 用户名 | 密码 | 说明 |
|------|--------|------|------|
| 学生 | `student` | `password123` | 课程查询、选课、校园服务 |
| 教师 | `teacher` | `password123` | 成绩录入、班级管理 |
| 管理员 | `admin` | `password123` | 系统管理、数据导出 |

> 生产环境请删除演示账户并使用强密码。

## 项目结构

```
├── backend/                # 后端服务
│   ├── agents/             # CrewAI 智能体定义
│   ├── api/v1/endpoints/   # API 接口端点
│   ├── core/               # 核心配置与数据库连接
│   ├── models/             # 数据库模型
│   ├── schemas/            # Pydantic 数据模式
│   ├── services/           # 业务逻辑服务
│   ├── scripts/            # 初始化脚本
│   └── tests/              # 测试用例
├── frontend/               # 前端应用
├── data/                   # 示例数据与向量库
└── docs/                   # 项目文档
```

## 贡献指南

1. Fork 本项目
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交代码：`git commit -m "feat: 添加某某功能"`
4. 推送分支：`git push origin feature/your-feature`
5. 提交 Pull Request

## 许可证

本项目为开源项目，仅供学习和研究使用。
