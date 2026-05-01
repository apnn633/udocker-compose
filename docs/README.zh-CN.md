# udocker-compose（中文）

[English](./README.md) | [中文](./README.zh-CN.md)

`udocker` 的 Docker Compose 兼容编排工具 —— **无需 root 权限**即可运行多容器应用。

## 这是什么？

`udocker` 允许非特权用户在没有 Docker 的情况下运行容器，但它没有 `docker-compose` —— 你需要手动管理每个容器、改写服务主机名，并自行完成各项联动配置。

**udocker-compose** 为 `udocker` 提供了类似 Compose 的编排能力，让你可以直接使用现有的 `docker-compose.yml` 文件。

## 功能特性

- 解析 `docker-compose.yml`（v2/v3 格式）—— 直接使用现有 Compose 文件
- 基于拓扑排序的依赖解析（`depends_on`）
- 通过注入 `/etc/hosts` 实现服务名解析 —— 无需把连接串中的 `postgres` 改成 `127.0.0.1`
- 命名卷管理（映射为本地目录）
- 支持前台/后台运行与日志管理
- 自动重启监控（`restart: always/unless-stopped`），仅在当前 `udocker-compose` 进程存活期间生效
- 健康检查
- 单文件实现，除 Python 3 + PyYAML 外无额外依赖

> **注意：** `udocker` 中所有容器都直接运行在宿主机网络上，**没有任何网络隔离**。注入 `/etc/hosts` 只是一个兼容性便利功能：把 `postgres`、`redis` 等服务名映射到 `127.0.0.1`，从而让现有 Compose 文件无需修改即可运行。它不提供虚拟网络，也不提供隔离。

## 快速开始

### 安装

```bash
# 1. 安装 udocker（如果尚未安装）
pip install udocker
udocker install

# 2. 安装 udocker-compose
git clone https://github.com/apnn633/udocker-compose.git
chmod +x udocker-compose/udocker-compose
ln -s $(pwd)/udocker-compose/udocker-compose ~/.local/bin/udocker-compose

# 3. 安装依赖
pip install pyyaml
```

### 使用方法

```bash
cd your-project/   # 包含 docker-compose.yml 的目录

udocker-compose up -d          # 后台启动所有服务
udocker-compose ps             # 查看服务状态
udocker-compose logs -f        # 实时跟踪日志
udocker-compose stop           # 停止服务（保留容器）
udocker-compose down           # 停止并删除容器
udocker-compose down -v        # 同时删除命名卷
```

## 命令列表

| 命令 | 说明 |
|------|------|
| `up [-d] [service...]` | 创建并启动服务，`-d` 表示后台运行 |
| `down [-v]` | 停止并删除容器，`-v` 同时删除命名卷 |
| `ps [service...]` | 查看服务状态 |
| `pull [service...]` | 拉取服务镜像 |
| `logs [-f] [-n N] [service...]` | 查看日志，`-f` 表示持续跟踪 |
| `restart [service...]` | 重启服务 |
| `stop [service...]` | 停止服务但不删除容器 |
| `start [service...]` | 启动已停止的服务 |
| `exec <service> <cmd>` | 在服务容器中执行命令 |
| `run [--rm] <service> <cmd>` | 运行一次性命令 |
| `config` | 校验并展示解析后的配置 |

## 服务名解析原理

在 Docker Compose 中，同一网络下的容器可以通过服务名互相访问，例如 `postgres:5432`。这是因为 Docker 会创建带有内置 DNS 的虚拟网络。

而 `udocker` **没有网络隔离** —— 所有容器都直接运行在宿主机网络栈上，共享端口和 IP。没有虚拟网络、没有独立容器 IP，也没有 DNS。

为了让你**无需改写连接串**就能使用现有的 `docker-compose.yml`，`udocker-compose` 会向每个容器注入一个 `/etc/hosts` 文件，把所有服务名都映射到 `127.0.0.1`：

```text
# 容器内自动生成的 /etc/hosts：
127.0.0.1   localhost
127.0.0.1   new-api   postgres   redis
```

因此 `postgresql://user:pass@postgres:5432/db` 可以直接工作 —— `postgres` 会解析到 `127.0.0.1`，而 postgres 进程本来就在该地址监听。**这不是网络能力，只是为了兼容 Compose 使用方式的主机名别名映射。**

### 这不提供什么？

- 不提供网络隔离 —— 所有服务对宿主机和彼此都可达
- 不提供独立容器 IP
- 不提供虚拟网络或 bridge 接口
- 两个服务不能绑定同一个端口，因为它们共享宿主机端口空间
- `1024` 以下端口仍然需要 root 权限

## 示例：多服务应用

给定如下 `docker-compose.yml`：

```yaml
version: '3.4'

services:
  app:
    image: myapp:latest
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://root:secret@postgres:5432/mydb
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
      - postgres

  redis:
    image: redis:latest

  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: root
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: mydb
    volumes:
      - pg_data:/var/lib/postgresql/data

volumes:
  pg_data:
```

```bash
$ udocker-compose config
Project: myproject
Startup order: postgres -> redis -> app

$ udocker-compose up -d
[+] Network: generated hosts file (3 service names)
[+] Starting: postgres -> redis -> app

SERVICE    CONTAINER           STATUS              PORTS
---------------------------------------------------------------
postgres   myproject_postgres  running (PID: 1234)
redis      myproject_redis     running (PID: 1235)
app        myproject_app       running (PID: 1236) 3000->3000/tcp

[+] app: http://localhost:3000
```

## 配置说明

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `UDOCKER_COMPOSE_UDOCKER` | `udocker` | `udocker` 可执行文件路径 |
| `UDOCKER_COMPOSE_EXECMODE` | `P1` | 执行模式（`P1`、`P2`、`F1-F4`、`R1-R3`、`S1`） |
| `UDOCKER_COMPOSE_DEBUG` | 未设置 | 设为 `1` 以启用调试输出 |

### 执行模式

`udocker` 支持多种执行后端，可根据环境选择：

| 模式 | 引擎 | 性能 | 适用场景 |
|------|------|------|----------|
| **P1**（默认） | PRoot + seccomp | 中 | 通用场景、Termux/Android |
| **P2** | PRoot（无加速） | 低 | P1 不可用时的后备方案 |
| **F1-F4** | Fakechroot | 高 | 对性能敏感的场景（不适用于 Termux） |
| **R1-R3** | runc/crun | 高 | 支持 user namespace 的系统 |
| **S1** | Singularity | 高 | HPC 集群 |

```bash
# 切换执行模式
UDOCKER_COMPOSE_EXECMODE=F1 udocker-compose up -d
```

### Compose 特性支持情况

| 特性 | 支持情况 | 备注 |
|------|----------|------|
| `image` | 支持 | |
| `build` | 不支持 | 需在其他环境构建后再使用 `udocker load` |
| `command` | 支持 | |
| `entrypoint` | 支持 | |
| `environment` | 支持 | 支持 dict 和 list 两种格式 |
| `env_file` | 支持 | |
| `volumes`（bind） | 支持 | 相对路径会自动解析 |
| `volumes`（named） | 支持 | 存储在 `.udocker-compose/volumes/` |
| `ports` | 支持 | 仅 Pn 模式，且使用宿主机网络 |
| `depends_on` | 支持 | 通过拓扑排序处理 |
| `restart` | 支持 | `always`、`unless-stopped` |
| `healthcheck` | 支持 | `CMD`、`CMD-SHELL` |
| `networks` | 部分支持 | 无隔离；服务名通过 `/etc/hosts` 映射到 `127.0.0.1` |
| `container_name` | 支持 | |
| `hostname` | 支持 | 通过环境变量传递 |
| `working_dir` | 支持 | |
| `user` | 支持 | |
| `devices` | 部分支持 | 仅 Rn 模式 |
| `shm_size` | 不支持 | |
| `privileged` | 不支持 | 无真实 root |
| `cap_add` | 不支持 | |

## 与 Docker Compose 的对比

| 方面 | Docker Compose | udocker-compose |
|------|---------------|-----------------|
| 是否需要 root | 是（或 docker 组权限） | 否 |
| 守护进程 | 需要 `dockerd` | 无守护进程 |
| 网络隔离 | 完整（veth + bridge） | **无** —— 所有服务共享宿主机网络 |
| 端口映射 | iptables NAT | 无需映射，端口直接绑定宿主机 |
| 镜像构建 | `docker build` | 不支持 |
| 命名卷 | Docker 管理 | 本地目录 |
| 重启策略 | `dockerd` 负责监控 | 后台线程监控 |
| 服务扩容 | `--scale` | 不支持 |
| Compose profiles | 支持 | 不支持 |

## 状态目录

`udocker-compose` 会在项目目录下的 `.udocker-compose/` 中存储运行时状态：

```text
.udocker-compose/
  ├── state.json          # 服务状态跟踪
  ├── pids/               # 运行中服务的 PID 文件
  │   ├── redis.pid
  │   └── postgres.pid
  ├── logs/               # 服务 stdout/stderr 日志
  │   ├── redis.log
  │   └── postgres.log
  ├── network/
  │   └── hosts           # 自动生成的 /etc/hosts 文件
  └── volumes/
      └── pg_data/        # 命名卷数据
```

## 重启行为说明

`restart: always` 和 `restart: unless-stopped` 是通过当前进程内的后台监控线程实现的，并不是持久化守护进程。因此，自动重启行为只在当前 `udocker-compose` 进程存活期间有效。

## 平台说明

### Termux / Android

- 仅支持 Pn 模式（推荐 `P1`）
- 若使用 Termux 自带的 `proot`，请设置 `UDOCKER_USE_PROOT_EXECUTABLE=$(which proot)`
- 不支持 user namespace，因此所有容器共享宿主机网络

### HPC / 计算集群

- 可用模式取决于集群配置
- 适合批处理作业环境
- 可通过 `udocker` 支持 MPI 集成

## 运行要求

- Python >= 3.7
- [PyYAML](https://pypi.org/project/PyYAML/)
- [udocker](https://github.com/indigo-dc/udocker) >= 1.3.0

## License

MIT
