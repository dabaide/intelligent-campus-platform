# 故障排除指南

## 常见问题和解决方案

---

## 1. 系统启动问题

### 问题: 前端无法启动

**症状**: 
- 端口3000被占用
- npm start 失败
- 提示"Something is already running on port 3000"

**解决方案**:
```powershell
# 清理所有Node进程
taskkill /F /IM node.exe

# 等待2秒
Start-Sleep -Seconds 2

# 重新启动前端
cd frontend
npm start
```

### 问题: 后端无法启动

**症状**:
- Uvicorn启动失败
- 端口8000被占用
- 数据库连接错误

**解决方案**:
```powershell
# 清理所有Python进程
taskkill /F /IM python.exe

# 等待2秒
Start-Sleep -Seconds 2

# 重新启动后端
cd backend
venv\Scripts\Activate.ps1
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 问题: 系统完全无响应

**症状**:
- 前后端都无法启动
- 多个进程卡住
- 需要完全重启

**解决方案**:
```powershell
# 清理所有相关进程
taskkill /F /IM python.exe 2>$null
taskkill /F /IM node.exe 2>$null
taskkill /F /IM uvicorn.exe 2>$null

# 等待3秒
Start-Sleep -Seconds 3

# 重新启动后端
cd backend
venv\Scripts\Activate.ps1
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# 在另一个终端启动前端
cd frontend
npm start
```

---

## 2. 登录问题

### 问题: 无法登录

**症状**:
- 提示"用户名或密码错误"
- 登录页面无法提交
- 后端返回401错误

**排查步骤**:

1. **验证演示账户是否存在**:
```bash
cd backend
python scripts/init_demo_users.py
```

2. **检查账户信息**:
   - 学生: student@example.com / password123
   - 教师: teacher@example.com / password123
   - 管理员: admin@example.com / password123

3. **验证后端API**:
```bash
# 测试登录API
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"student@example.com","password":"password123"}'
```

4. **如果仍然失败，执行完全重置**:
```powershell
# 关闭后端
taskkill /F /IM python.exe

# 删除数据库
Remove-Item "backend/data/campus.db" -Force -ErrorAction SilentlyContinue

# 重新启动后端
cd backend
venv\Scripts\Activate.ps1
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# 在另一个终端初始化演示账户
cd backend
python scripts/init_demo_users.py

# 导入知识库
python scripts/import_hbue_knowledge.py
```

5. **刷新浏览器**:
   - 清除浏览器缓存 (Ctrl+Shift+Delete)
   - 硬刷新页面 (Ctrl+Shift+R)
   - 重新尝试登录

### 问题: 登录后立即退出

**症状**:
- 登录成功但立即跳转到登录页
- Token无效或过期
- 前端无法保存token

**解决方案**:
1. 清除浏览器缓存和Cookies
2. 检查浏览器控制台错误
3. 查看后端日志
4. 重新启动前后端

### 问题: 忘记密码

**症状**:
- 无法重置密码
- 忘记演示账户密码

**解决方案**:
1. 重新初始化演示账户:
```bash
python scripts/init_demo_users.py
```

2. 使用新密码登录: password123

---

## 3. 数据库问题

### 问题: 数据库连接失败

**症状**:
- "DatabaseError" 或 "Connection refused"
- 无法查询数据
- 后端启动失败

**解决方案**:
1. 检查数据库文件位置
2. 验证数据库权限
3. 检查SQLite是否正确安装
4. 查看后端日志获取详细错误

### 问题: 数据库被锁定

**症状**:
- "database is locked" 错误
- 无法写入数据
- 多个进程访问同一数据库

**解决方案**:
1. 关闭所有后端进程
2. 等待2-3秒
3. 重新启动后端

---

## 4. API问题

### 问题: API返回500错误

**症状**:
- "Internal Server Error"
- 后端日志显示异常
- 特定API端点失败

**排查步骤**:
1. 查看后端日志获取错误详情
2. 检查请求参数是否正确
3. 验证用户权限
4. 检查数据库状态

### 问题: API超时

**症状**:
- 请求无响应
- 浏览器显示"连接超时"
- 后端进程卡住

**解决方案**:
1. 检查后端是否正在运行
2. 查看系统资源使用情况
3. 重启后端服务
4. 检查网络连接

---

## 5. 前端问题

### 问题: 页面无法加载

**症状**:
- 白屏或错误页面
- 浏览器控制台有JavaScript错误
- 资源加载失败

**解决方案**:
1. 清除浏览器缓存
2. 硬刷新页面 (Ctrl+Shift+R)
3. 检查浏览器控制台错误
4. 检查网络选项卡查看失败的请求

### 问题: 样式或图片无法加载

**症状**:
- 页面布局混乱
- 图片显示为破损
- CSS未应用

**解决方案**:
1. 检查网络连接
2. 清除浏览器缓存
3. 检查前端编译是否成功
4. 重启前端服务

### 问题: 功能按钮无响应

**症状**:
- 点击按钮无反应
- 表单无法提交
- 页面交互失效

**排查步骤**:
1. 打开浏览器开发者工具
2. 查看控制台错误
3. 检查网络请求
4. 验证后端API是否正常

---

## 6. 性能问题

### 问题: 系统响应缓慢

**症状**:
- 页面加载慢
- API响应时间长
- 搜索结果延迟

**优化方案**:
1. 检查缓存是否启用
2. 查看系统资源使用情况
3. 检查数据库查询性能
4. 考虑增加缓存过期时间

### 问题: 高CPU或内存使用

**症状**:
- 系统卡顿
- 进程占用大量资源
- 系统变慢

**解决方案**:
1. 重启后端和前端
2. 检查是否有内存泄漏
3. 清理缓存
4. 查看日志找出问题

---

## 7. 知识库问题

### 问题: 无法创建文档

**症状**:
- 创建文档API返回错误
- 权限不足
- 数据库错误

**解决方案**:
1. 确保使用管理员账户
2. 检查请求参数
3. 查看后端日志
4. 验证数据库连接

### 问题: 知识库显示为空或搜索无结果

**症状**:
- 知识库页面显示"0条目"
- 搜索返回空结果
- 热门问题和知识分类为空

**解决方案**:

1. **验证数据是否导入**:
```bash
cd backend
python scripts/import_hbue_knowledge.py
```

2. **刷新浏览器**:
   - 清除浏览器缓存 (Ctrl+Shift+Delete)
   - 硬刷新页面 (Ctrl+Shift+R)

3. **检查后端API**:
```bash
# 测试获取FAQ API
curl -X GET http://localhost:8000/api/v1/knowledge/faqs/popular \
  -H "Authorization: Bearer <token>"

# 测试获取文档API
curl -X GET http://localhost:8000/api/v1/knowledge/documents \
  -H "Authorization: Bearer <token>"
```

4. **如果仍然无效，执行完全重置**:
```powershell
# 关闭后端
taskkill /F /IM python.exe

# 删除数据库
Remove-Item "backend/data/campus.db" -Force -ErrorAction SilentlyContinue

# 重新启动后端
cd backend
venv\Scripts\Activate.ps1
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# 重新初始化演示账户和导入知识库
cd backend
python scripts/init_demo_users.py
python scripts/import_hbue_knowledge.py
```

5. **刷新浏览器并重新登录**

---

## 8. 快速诊断

### 系统健康检查

```bash
# 检查后端健康状态
curl http://localhost:8000/health

# 检查API文档
curl http://localhost:8000/docs

# 测试登录
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"student@example.com","password":"password123"}'
```

### 日志位置

- **后端日志**: 终端输出
- **前端日志**: 浏览器开发者工具 > 控制台
- **数据库日志**: 后端日志中的SQLAlchemy输出

---

## 9. 快速修复

### 知识库修复脚本（推荐）

如果知识库显示为空，运行此脚本：

```powershell
# 在项目根目录运行
.\fix_knowledge_base.ps1
```

**脚本会自动执行以下操作**:
1. ✅ 重新导入知识库数据
2. ✅ 打开浏览器自动清除缓存
3. ✅ 显示验证步骤

### 完全修复脚本

如果遇到登录或知识库问题，可以运行完全修复脚本：

```powershell
# 在项目根目录运行
.\quick_fix.ps1
```

**脚本会自动执行以下操作**:
1. ✅ 清理所有旧进程
2. ✅ 删除旧数据库
3. ✅ 启动后端服务
4. ✅ 初始化演示账户
5. ✅ 导入知识库数据
6. ✅ 启动前端应用

脚本完成后，按照提示操作即可。

### 手动重新初始化系统

如果不想使用脚本，可以手动执行以下步骤：

```bash
# 1. 清理所有进程
taskkill /F /IM python.exe 2>$null
taskkill /F /IM node.exe 2>$null

# 2. 清理数据库
Remove-Item "backend/data/campus.db" -Force -ErrorAction SilentlyContinue

# 3. 启动后端
cd backend
venv\Scripts\Activate.ps1
uvicorn main:app --reload --host 127.0.0.1 --port 8000

# 4. 在另一个终端初始化演示账户
cd backend
python scripts/init_demo_users.py

# 5. 导入知识库数据
python scripts/import_hbue_knowledge.py

# 6. 在第三个终端启动前端
cd frontend
npm start
```

---

## 10. 获取帮助

### 查看相关文档

- [系统就绪指南](SYSTEM_READY.md)
- [演示账户说明](DEMO_ACCOUNTS.md)
- [测试指南](TESTING_GUIDE.md)
- [功能完善说明](FEATURE_ENHANCEMENTS.md)

### 检查日志

1. **后端日志**: 查看启动后端的终端窗口
2. **前端日志**: 打开浏览器开发者工具 (F12) > 控制台
3. **网络日志**: 浏览器开发者工具 > 网络选项卡

### 常见错误代码

| 错误代码 | 含义 | 解决方案 |
|---------|------|---------|
| 401 | 未授权 | 检查登录状态和token |
| 403 | 禁止访问 | 检查用户权限 |
| 404 | 未找到 | 检查API端点和参数 |
| 500 | 服务器错误 | 查看后端日志 |
| 503 | 服务不可用 | 检查后端是否运行 |

---

**最后更新**: 2026年5月30日  
**版本**: 1.0.0
