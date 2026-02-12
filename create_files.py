#!/usr/bin/env python3
"""
创建小红书文案和优化后的 README 文件
"""

xiaohongshu_content = """# 小红书推广文案 - Docker 私有仓库管理系统

## 标题
🚀 自建 Docker 私有仓库管理神器！轻量级、功能强，一键批量管理镜像～

## 正文内容

### 👋 开篇
最近在折腾 Docker 容器化部署，需要一个私有仓库来管理自家镜像。网上找了一圈，发现要么功能太简单，要么配置太复杂。索性自己动手做了一个轻量级的可视化管理系统，今天分享给大家！✨

### 🎯 核心功能亮点
**1️⃣ 可视化管理界面**
基于 Docker Registry v2 API 开发，无需记复杂的命令行，点点鼠标就能搞定：
- 浏览仓库列表和镜像 Tag
- 按需删除指定镜像
- 实时查看仓库健康状态

**2️⃣ 远程镜像同步**
从 Docker Hub 或其他镜像源一键拉取并推送到私有仓库：
```
输入源镜像：nginx:1.27
设置目标仓库：platform/nginx
点击「开始同步」即可自动完成 pull → tag → push
```

**3️⃣ 本地镜像批量处理** ⭐
这是我最喜欢的功能！扫描本地镜像后，可以：
- ✅ 一键批量上传到私有仓库
- ✅ 自动识别架构并添加标签后缀（-x86 / -arm）
- ✅ 批量添加/移除仓库前缀（如统一加上 x86/ 或 arm/）
- ✅ 上传后自动清理本地旧标签，保持整洁

**4️⃣ 远程仓库一键重命名**
按前缀批量重命名远程仓库的所有 tags，再也不用一个一个手动改了！
- 例如：把所有 `nginx/` 开头的仓库统一改成 `platform/nginx/`
- 可选开启「重命名后删除旧标签」，避免新旧仓库并存

**5️⃣ 实时任务监控**
所有操作都有实时日志输出，随时查看任务执行进度和结果～

### 📦 适用场景
✅ **个人开发者**：搭建家庭实验室，管理自建应用的 Docker 镜像
✅ **小团队**：私有化部署，统一管理团队项目的镜像仓库
✅ **多架构环境**：同时管理 x86 和 ARM 架构的镜像，自动识别标签
✅ **镜像批处理**：需要批量重命名、上传、删除大量镜像标签

### 🛠️ 快速上手
**第一步：启动服务**
```bash
docker compose up --build -d
```

**第二步：访问管理页面**
打开浏览器访问：`http://localhost:8080`

**第三步：开始管理**
- 左侧面板浏览仓库列表
- 中间查看镜像 Tag 信息
- 右侧进行镜像同步和批量上传操作

### 💡 技术栈
- **后端**：Python + FastAPI
- **前端**：原生 HTML/CSS/JavaScript（无框架，轻量级）
- **协议**：Docker Registry HTTP API v2
- **部署**：Docker + docker-compose

### 🎁 特色设计
- 🎨 现代化 UI 设计，渐变背景 + 毛玻璃效果
- 📱 响应式布局，支持移动端访问
- 🔐 挂载宿主机 `/var/run/docker.sock`，直接操作 Docker
- ⚡ 支持分页查询，轻松管理大量仓库
- 🧹 智能清理，同步后自动删除临时镜像

## 总结
这个项目解决了我自建 Docker 仓库管理的痛点，界面简洁、功能实用，特别适合需要批量管理镜像的场景。代码开源，欢迎大家一起完善！💪

## 标签
#Docker #私有仓库 #DevOps #容器管理 #DockerRegistry #开源项目 #技术分享 #自建服务

## 配图说明
> 请使用项目根目录下的 `screenshot.png` 作为配图，展示管理界面的实际效果。
> 如需重新生成截图，运行以下命令：
> ```bash
> npm install puppeteer
> node screenshot.js
> ```

## 项目地址
🔗 GitHub：[项目地址待填写]

## 互动引导
👇 **你的 Docker 私有仓库是怎么管理的？有什么好用的工具推荐？**
欢迎在评论区分享你的经验～
喜欢这个项目的话，别忘了点赞收藏哦！❤️
"""

readme_content = """# Docker Private Registry Manager

> 一个轻量级、功能强大的 Docker 私有仓库可视化管理系统

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📸 项目截图

![管理界面](./screenshot.png)

> *现代化 UI 设计，毛玻璃效果 + 渐变背景，界面简洁易用*

---

## ✨ 核心特性

| 功能 | 描述 |
|------|------|
| 🔍 **仓库浏览** | 基于 Registry HTTP API v2，可视化浏览仓库列表和镜像 Tag |
| 🗑️ **镜像删除** | 解析 digest 后精确删除指定镜像 |
| 🔄 **远程同步** | 从外部镜像源一键拉取并推送到私有仓库（pull → tag → push） |
| 📦 **批量上传** | 扫描本地 Docker 镜像，一键批量重命名并推送到私有仓库 |
| 🏷️ **前缀管理** | 统一添加/移除仓库前缀（如 `x86/`、`arm/`、`prod/`） |
| 🔄 **远程重命名** | 一键按前缀批量重命名远程仓库的所有 tags |
| 📊 **实时日志** | 任务执行日志实时查看，监控每个操作状态 |
| 🏗️ **跨架构** | 自动识别宿主机架构并追加标签后缀（`-x86` / `-arm`） |

---

## 📦 快速开始

### 方式 A：连接你已有的私有仓库（推荐）

`docker-compose.yml` 默认已配置为连接私有仓库：

```bash
docker compose up --build -d
```

启动后访问管理页面：

- **管理界面**: `http://localhost:8080`

---

### 方式 B：完整本地栈（registry + redis + manager）

如果你想在本机完整测试，可使用：

```bash
docker compose -f docker-compose.full.yml up --build -d
```

启动后访问：

- **Registry API**: `http://localhost:5000`
- **管理界面**: `http://localhost:8080`

---

## ⚙️ 配置说明

### 关键环境变量

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `REGISTRY_API_URL` | Registry API 地址 | `http://registry:5000` |
| `REGISTRY_PUSH_HOST` | 推送目标地址 | `192.168.5.54:5000` |
| `REQUEST_TIMEOUT_SEC` | Registry API 超时（秒） | `20` |
| `MAX_CATALOG_RESULTS` | 每页最多仓库数 | `200` |
| `SYNC_JOB_RETENTION` | 内存中保留的任务数量 | `120` |

---

## 🚀 功能详解

### 1. 远程镜像同步

在「远程镜像同步」面板中，填写以下信息：

- **源镜像**：例如 `nginx:1.27`
- **目标仓库**（可选）：例如 `platform/nginx`
- **目标标签**（可选）：例如 `stable`

点击「开始同步」后，系统会在服务容器内执行：

```bash
docker pull <source_image>
docker tag <source_image> <REGISTRY_PUSH_HOST>/<target_repo>:<target_tag>
docker push <REGISTRY_PUSH_HOST>/<target_repo>:<target_tag>
```

可选开启「同步完成后清理本地镜像标签」，自动清理同步过程中产生的临时镜像。

---

### 2. 本地镜像批量上传

在「本地镜像批量上传」面板中：

1. 点击「扫描本地镜像」获取本地 Docker 镜像列表
2. 勾选目标镜像
3. 选择 **Arch mode**（架构处理模式）：
   - `Auto`：自动识别宿主机架构并追加标签后缀（`-x86` / `-arm`）
   - `Custom`：自定义后缀
   - `None`：不追加架构后缀
4. 选择 **Prefix mode**（前缀处理模式）：
   - `add`：统一给 repository 增加前缀
   - `remove`：统一去掉 repository 前缀
   - `none`：不改前缀
5. 点击「上传已选镜像」一键上传

**示例**：

```
原镜像：nginx:1.27
Arch mode=auto（识别为 x86）
Prefix mode=add，prefix=x86
推送结果：192.168.5.54:5000/x86/nginx:1.27-x86
```

**清理选项**：

- ✅ **上传成功后删除本地旧标签**：推送成功后删除本地旧标签（只删标签，不删已被其他标签引用的镜像层）
- ✅ **上传成功后删除仓库旧标签**：推送成功后删除仓库中旧 tag，减少新旧命名并存

---

### 3. 远程仓库一键重命名

在「仓库列表」面板中：

1. 勾选要处理的远程仓库（可全选可见仓库）
2. 选择前缀模式（添加/移除）并填写前缀值
3. 点击「一键远程重命名」

系统会对选中仓库下所有 tags 执行：

```bash
docker pull <registry>/<old-repo>:<tag>
docker tag <registry>/<old-repo>:<tag> <registry>/<new-repo>:<tag>
docker push <registry>/<new-repo>:<tag>
```

可选开启「重命名成功后删除旧仓库标签」，避免新旧仓库并存。

---

### 4. 本地镜像批量删除

在「本地镜像批量上传」面板中，勾选本地镜像后可点击「删除已选镜像」：

- 系统会把所选 `repo:tag` 映射为本地 `image_id`，并去重后执行：`docker image rm -f <image_id>`
- 删除任务会进入最近任务列表并输出日志
- 单项失败不会中断后续项，最后汇总失败数量
- 由于按 `image_id` 强制删除，可能影响同一 ID 下的多个标签

---

## 🔧 API 设计依据

项目基于 Docker Registry HTTP API v2 开发，核心使用了以下接口：

| 接口 | 说明 |
|------|------|
| `GET /v2/_catalog?n=&last=` | 获取仓库列表（支持分页） |
| `GET /v2/<name>/tags/list` | 获取 Tag 列表 |
| `HEAD /v2/<name>/manifests/<reference>` | 读取 `Docker-Content-Digest` |
| `GET /v2/<name>/manifests/<reference>` | 读取 manifest 内容 |
| `DELETE /v2/<name>/manifests/<digest>` | 删除 manifest |
| `GET /v2/<name>/blobs/<digest>` | 读取 config blob（提取构建时间） |

**应用新增接口**：

| 接口 | 说明 |
|------|------|
| `GET /api/local-images` | 读取本地 Docker 镜像列表 |
| `POST /api/local-push-jobs` | 批量执行本地镜像 `tag + push` |
| `POST /api/local-delete-jobs` | 按镜像 ID 批量删除本地镜像 |
| `POST /api/remote-prefix-jobs` | 远程仓库按前缀批量重命名 |

---

## 📁 项目结构

```
docker-mirrors-pravite-manager/
├── app/
│   ├── main.py              # FastAPI 主应用（所有 API 路由）
│   ├── registry_client.py   # Registry v2 API 客户端
│   ├── sync_jobs.py         # 同步任务管理器
│   ├── config.py            # 配置管理（环境变量）
│   └── static/
│       ├── index.html       # 前端主页面
│       ├── app.js           # 前端逻辑
│       └── styles.css       # 样式表
├── Dockerfile               # 容器构建配置
├── docker-compose.yml       # 服务编排配置
├── docker-compose.full.yml  # 完整栈配置
├── requirements.txt         # Python 依赖
├── screenshot.py            # Python 截图脚本
├── screenshot.js            # Node.js 截图脚本
└── README.md                # 项目文档
```

---

## ❓ 常见问题

### Q: Registry 删除镜像后空间没有释放？
A: Registry 删除 manifest 后，存储空间需要执行垃圾回收才会真正释放。这是 Registry 的机制，不是 UI 限制。

### Q: 同步任务失败怎么办？
A: 检查以下几点：
1. 宿主机 Docker daemon 对私有仓库地址是否正确配置（如 insecure registry 或 TLS 证书）
2. 网络连接是否正常
3. 源镜像是否存在且可访问

### Q: 批量删除会影响其他标签吗？
A: 批量删除按 `image_id` 强制删除，可能影响同一 ID 下的多个标签。请谨慎操作。

### Q: 如何管理大量仓库？
A: 系统支持分页查询，默认每页显示 200 个仓库。可通过环境变量 `MAX_CATALOG_RESULTS` 调整。

---

## 🛡️ 安全注意事项

- 通过挂载 `/var/run/docker.sock` 直接操作宿主机 Docker，请确保容器环境安全
- 建议在内网环境使用，或配置适当的访问控制和 HTTPS
- 批量删除和重命名操作不可逆，请谨慎执行

---

## 📄 技术栈

- **后端**: Python 3.12 + FastAPI 0.115.12
- **HTTP 客户端**: httpx 0.28.1
- **Web 服务器**: uvicorn 0.34.0
- **前端**: 原生 HTML/CSS/JavaScript（无框架）
- **容器化**: Docker + docker-compose
- **协议**: Docker Registry HTTP API v2

---

## 📝 License

MIT License

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📞 联系方式

如有问题或建议，欢迎通过 Issue 联系。
"""

# 写入文件
with open('xiaohongshu_post.md', 'w', encoding='utf-8') as f:
    f.write(xiaohongshu_content)
    print('✓ 已创建 xiaohongshu_post.md')

with open('README.md', 'w', encoding='utf-8') as f:
    f.write(readme_content)
    print('✓ 已更新 README.md')

print('\n所有文件创建完成！')
