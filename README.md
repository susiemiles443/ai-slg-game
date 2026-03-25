# SLG AI 对话游戏 v1

单人 SLG 网页游戏，玩家输入偏好与回合策略，后端通过 OpenAI 兼容接口生成剧情、NPC 行为、动态事件，并把战局存档与回合快照保存到 PostgreSQL。

## 架构

- 前端：`HTML + CSS + Vanilla JS`
- 后端：`FastAPI`
- 数据库：`PostgreSQL`
- 部署：`Docker Compose`（`nginx + backend + db`）

## 目录

- `frontend/` 静态页面
- `backend/` API 服务
- `nginx/default.conf` 反向代理与静态托管
- `docker-compose.yml` 容器编排

## 本地启动

1. 复制环境变量文件：

```bash
cp .env.example .env
```

2. 修改 `.env`：
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `TURN_TOKEN_BUDGET`（默认 20000）

3. 启动：

```bash
docker compose up -d --build
```

4. 访问：
- 前端：`http://<服务器IP或域名>/`
- API 文档：`http://<服务器IP或域名>/docs`

## 核心接口

- `GET /api/health` 健康检查
- `POST /api/games` 创建战局（会生成 Turn 0 快照）
- `GET /api/games?player_id=...` 列出当前玩家所有存档（不限槽位）
- `GET /api/games/{game_id}?player_id=...` 获取战局详情
- `POST /api/games/{game_id}/turn` 推进回合（自动快照）
- `GET /api/games/{game_id}/snapshots?player_id=...` 回合历史

## 云服务器部署建议

1. 安装 Docker 与 Compose 插件。
2. 上传项目并配置 `.env`。
3. 执行 `docker compose up -d --build`。
4. 若你已有 HTTPS 证书，可使用主机 Nginx/Caddy 反代到本项目 `80` 端口，或将证书挂载到容器版 Nginx 再监听 `443`。

## 说明

- 当前版本无账号系统，使用前端 `localStorage` 里的 `player_id` 识别单玩家。
- 每回合会按预算估算 token，超过预算时会拒绝请求。
