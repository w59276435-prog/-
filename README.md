# 个人信息自动处理存档导出工具（可运行 MVP）

这是一个**完整可运行**的最小版本，包含后端 API + 现代化前端页面，支持：

- 人员新增、查询、删除
- 关键字搜索（姓名/部门/标签）
- CSV 批量导入
- CSV 一键导出
- 首页统计（人员总数、部门数）

## 技术实现

- 后端：FastAPI + SQLAlchemy + SQLite
- 前端：静态 HTML + 原生 JS（现代化卡片与表格 UI）
- 存储：本地 SQLite（`data.db`）

## 快速启动

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

启动后访问：

- 页面：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/api/health`

## CSV 导入格式

上传 CSV 时请使用以下表头：

```csv
name,department,tag
张三,研发部,骨干
李四,人事部,
```

## API 概览

- `GET /api/health`
- `GET /api/stats`
- `GET /api/people?keyword=xxx`
- `POST /api/people`
- `PATCH /api/people/{id}`
- `DELETE /api/people/{id}`
- `POST /api/import/csv`
- `GET /api/export/csv`
