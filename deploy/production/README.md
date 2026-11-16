# 个人服务器部署

此目录将前端、API、预测服务部署为独立的 `backing` Compose 项目，不修改宿主机驱动、Docker 数据目录或现有 `jl` 容器。站点入口为 `https://125.122.98.226:2939`，只有 Nginx 发布端口（2939 → 443）。API 8808 和预测服务 8211 仅容器网络可见。

## 文件与持久化

服务器目录 `/home/yanxx/backing`：

| 路径 | 用途 |
| --- | --- |
| `source/` | 本次发布的源码及部署脚本 |
| `frontend/` | Vite 生产构建，无密钥 |
| `deployment.env` | Compose 的版本、路径、镜像、GPU UUID（不含业务凭证） |
| `shared/config/backend.env` | 后端生产配置及 AI 凭证，权限 600 |
| `shared/config/predictor.env` | 内部预测服务认证，权限 600 |
| `shared/db/stock_backtest.db` | 已迁移的独立数据库副本 |
| `shared/backend-data/` | 研究工件、运行报告 |
| `shared/tls/` | 站点证书、CA 和私钥；不要公开私钥 |
| `models/` | 固定版本模型、上游源码和校验清单 |
| `backups/` | 每日私有备份，保留 14 天 |
| `release.json` | 实际源码包和镜像版本清单 |

`BACKING_ENV_FILE` 将配置加载和网页 AI 设置写入指向同一文件。默认本地开发仍读取 `backend/.env`。挂载整个可写配置目录，避免原子改写 `.env` 后 Docker 单文件挂载失效。不要把 AI 密钥同时写进 Compose `environment`，否则旧环境变量会覆盖文件更新。

本地和服务器不再双向同步。数据库、凭证、证书私钥、备份不能提交到 Git。生产要求 `APP_ENV=production`、独立 `SESSION_SECRET`、`SESSION_HTTPS_ONLY=true`。

## 启停、日志与状态

以 `yanxx` 登录后：

```bash
cd /home/yanxx/backing
dc() { docker compose --env-file deployment.env -f source/deploy/production/compose.yaml "$@"; }
dc up -d
dc ps
dc logs --tail 100 backend predictor web
dc stop                 # 仅停止 backing 项目
dc up -d                # 重新启动
dc up -d --force-recreate backend
```

Nginx 使用 Docker 内部 DNS，后端重建后自动重新解析。容器设置 `unless-stopped`，随 Docker 启动恢复；主动停止的容器需手动 `up -d`。Docker 日志每服务最多 3 × 20MB。

后端单进程，任务使用既有 threads 机制；预测单进程并串行推理，仅映射物理 GPU 1 的 UUID，容器中是 `cuda:0`。模型空闲 600 秒卸载，不修改其他 GPU。

## 证书信任与续期

只分发 `ca.crt` / `backing-personal-ca.cer` / `.pem`，切勿分发 `ca.key` 或 `server.key`。

Windows：双击公开 `.cer` → 安装证书 → 当前用户 → 将所有证书放入“受信任的根证书颁发机构”，核对交付的 SHA256 指纹后确认。也可手动执行：

```powershell
certutil -user -addstore Root .\backing-personal-ca.cer
```

macOS：导入“钥匙串访问”的登录钥匙串，核对指纹后对该 CA 设置信任。Firefox 如使用独立证书库，需要在证书管理器的“证书颁发机构”中导入。手机需在系统证书设置中手动信任；iOS 导入后还需在“证书信任设置”开启该 CA。

站点证书包含公网 IP SAN，有效期 1 年，CA 有效期 5 年。到期前用现有 CA 签发新站点证书（无需重装 CA）：

```bash
cd /home/yanxx/backing/shared/tls
umask 077
openssl req -new -newkey rsa:3072 -nodes -keyout server.new.key \
  -out server.csr -subj /CN=125.122.98.226
printf 'subjectAltName=IP:125.122.98.226\nextendedKeyUsage=serverAuth\nbasicConstraints=critical,CA:FALSE\n' > server.ext
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
  -days 365 -sha256 -extfile server.ext -out server.new.crt
cat ca.crt >> server.new.crt
mv server.new.key server.key
mv server.new.crt server.crt
cd /home/yanxx/backing
dc exec -T web nginx -t
dc exec -T web nginx -s reload
```

先定义上一节 `dc` 函数。替换前执行一次备份；保留 CA 私钥的离线安全副本。

## 定时更新和备份

systemd 系统计时器以 `yanxx` 身份运行，时间显式为 `Asia/Shanghai`：

- `backing-sync.timer`：周一至周五 16:30，仅自选股，更新交易日历、行情和公司行动元数据；遵循现有数据源及已完成交易日规则。BaoStock 当日收盘数据通常 17:30 发布，因此 16:30 运行可能只补齐前一交易日，不伪造当天行情。
- `backing-backup.timer`：每日 03:30，SQLite 在线快照、配置、证书、研究工件、版本清单；保留 14 天。备份含凭证，只能私下保管。

```bash
systemctl list-timers backing-sync.timer backing-backup.timer
sudo systemctl start backing-sync.service
journalctl -u backing-sync.service -n 60 --no-pager
python3 /home/yanxx/backing/source/deploy/production/operations.py backup
```

同步报告在 `shared/backend-data/daily-sync-report.json`，定时任务输出在 `ops/sync.log` 和 `ops/backup.log`，按日轮转、超过 10MB 时轮转，保留 14 份。失败以非零状态保留在 systemd journal；没有新增通知/发布流水线。

下载备份（在自己的电脑执行，文件含密钥）：

```bash
scp yanxx@125.122.98.226:/home/yanxx/backing/backups/backing-实际时间.tar.gz .
```

## 恢复与回滚

先检查备份，不改正在使用的数据：

```bash
cd /home/yanxx/backing
python3 source/deploy/production/operations.py verify --archive backups/backing-实际时间.tar.gz
```

确认恢复时，暂停计时器和所有手工同步/研究任务，再执行：

```bash
sudo systemctl stop backing-sync.timer backing-backup.timer backing-sync.service
python3 source/deploy/production/operations.py restore \
  --archive backups/backing-实际时间.tar.gz --confirm-restore
sudo systemctl start backing-sync.timer backing-backup.timer
dc ps
```

恢复前自动保留一次当前在线备份，然后停止本项目容器，替换数据库、配置、证书及工件，重建服务；原本地数据始终不变。恢复命令不自动换代码/镜像：如跨版本恢复，请先参考备份内 `release.json` / `deployment.env` 选择对应源码和镜像，再由既有 Alembic 执行迁移。不要对旧版本数据库盲目降级。

## 首次构建

Compose 插件安装在用户目录并核对官方 SHA256。源码包必须包含当前未提交的部署文件；构建上下文使用 `context.dockerignore` 作为 `.dockerignore`，排除数据库、密钥和本地工件。前端用锁文件安装构建，不将演示数据写进生产代码。

先准备持久化 Linux 轮包，再离线构建，下载中断可以重试并复用已完成文件：

```bash
cd /home/yanxx/backing
for service in backend predictor; do
  docker run --rm -v "$PWD/source:/app" "$PYTHON_IMAGE" \
    bash /app/deploy/production/prepare-wheels.sh "$service"
done
dc build
```

`PYTHON_IMAGE` 使用 `deployment.env` 中实际已拉取的基础镜像。镜像和软件源访问受限时，本部署使用可达的 DaoCloud 镜像和清华 Debian/PyPI 镜像，不修改宿主机 Docker 配置。轮包缓存不进入运行镜像；依赖通过多阶段构建安装。

`backend.Dockerfile` 使用 Linux CPU Torch 和仓库依赖锁，将锁中的本机 mootdx 引用替换为从本仓库 vendored 补丁源码构建的 `0.11.7.post1` 轮包，始终不使用 PyPI mootdx。嵌套 TradingAgents 以 `--no-deps` 安装，保留后端既有的锁定环境和原有可选依赖范围。`predictor.Dockerfile` 使用独立 GPU 锁；模型由 `provision_models.py` 根据 `deploy/kronos/versions.json` 下载并校验，通过 SSH 离线传入。两套环境互不混装。

公网前提：路由器/云侧放行并转发 TCP `125.122.98.226:2939` → `192.168.0.3:2939`。仅服务器本机能访问不等于公网验收通过，不要公开后端和模型端口。
