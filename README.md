# Docker Private Registry Manager

一个可视化 Docker Registry 管理界面，支持：

- 浏览仓库与 Tag（基于 Registry HTTP API v2）
- 按 Tag 删除镜像（先解析 digest，再调用 `DELETE /manifests/{digest}`）
- 从外部镜像源拉取镜像并推送到你自己的仓库（`docker pull -> tag -> push`）
- 扫描本地 Docker 镜像，一键批量重命名并推送到私有仓库
- 批量前缀加/减（例如统一加 `x86/` 或 `arm/` 前缀）
- 任务日志实时查看

## 1. API 设计依据（Registry v2）

核心使用了以下接口：

- `GET /v2/_catalog?n=&last=`：获取仓库列表
- `GET /v2/<name>/tags/list`：获取 Tag 列表
- `HEAD /v2/<name>/manifests/<reference>`：读取 `Docker-Content-Digest`
- `GET /v2/<name>/manifests/<reference>`：读取 manifest 内容
- `DELETE /v2/<name>/manifests/<digest>`：删除 manifest
- `GET /v2/<name>/blobs/<digest>`：读取 config blob（提取构建时间）

应用新增接口：

- `GET /api/local-images`：读取本地 Docker 镜像列表
- `POST /api/local-push-jobs`：批量执行本地镜像 `tag + push`

## 2. 启动方式

### 方式 A：连接你已有的私有仓库（推荐）

`docker-compose.yml` 默认已配置为连接 `192.168.5.54:5000`：

```bash
docker compose up --build -d
```

启动后：

- 管理页面: `http://localhost:8080`

### 方式 B：完整本地栈（registry + redis + manager）

如果你想在本机完整测试，可使用：

```bash
docker compose -f docker-compose.full.yml up --build -d
```

启动后：

- Registry API: `http://localhost:5000`
- 管理页面: `http://localhost:8080`

## 3. 关键环境变量

- `REGISTRY_API_URL`：Registry API 地址（示例：`http://registry:5000`）
- `REGISTRY_PUSH_HOST`：推送目标地址（示例：`192.168.5.54:5000`）
- `REQUEST_TIMEOUT_SEC`：Registry API 超时
- `MAX_CATALOG_RESULTS`：每页最多仓库数
- `SYNC_JOB_RETENTION`：内存中保留的任务数量

## 4. 镜像同步说明

Web 中创建同步任务时，会在服务容器内执行：

1. `docker pull <source_image>`
2. `docker tag <source_image> <REGISTRY_PUSH_HOST>/<target_repo>:<target_tag>`
3. `docker push <REGISTRY_PUSH_HOST>/<target_repo>:<target_tag>`

由于调用宿主机 Docker（通过挂载 `/var/run/docker.sock`），请确保宿主机 Docker daemon 对私有仓库地址已正确配置（例如 insecure registry 或 TLS 证书）。

## 5. 本地镜像批量重命名并上传

在页面的 `Local Images Batch Push` 面板中：

1. 扫描本地镜像并勾选目标镜像。
2. 选择 `Arch mode`：
   - `Auto`：自动识别宿主机架构并追加 tag 后缀（`-x86` / `-arm`）
   - `Custom`：自定义后缀
   - `None`：不追加架构后缀
3. 选择 `Prefix mode`：
   - `add`：统一给 repository 增加前缀
   - `remove`：统一去掉 repository 前缀
   - `none`：不改前缀
4. 点击 `Push Selected` 一键上传。
5. 可选清理：
   - `Upload success then remove local old tag`：推送成功后删除本地旧标签（只删标签，不删已被其他标签引用的镜像层）。
   - `Upload success then remove registry old tag`：推送成功后删除仓库中旧 tag，减少新旧命名并存。

示例：

- 原镜像：`nginx:1.27`
- `Arch mode=auto`（识别为 `x86`）
- `Prefix mode=add`，`prefix=x86`
- 推送结果：`192.168.5.54:5000/x86/nginx:1.27-x86`

## 6. 删除后空间回收

Registry 删除 manifest 后，存储空间通常需要执行垃圾回收才会真正释放（这是 Registry 的机制，不是 UI 限制）。
