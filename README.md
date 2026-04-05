# udocker-compose

Docker Compose compatible orchestration tool for [udocker](https://github.com/indigo-dc/udocker) — run multi-container applications **without root privileges**.

## Why?

udocker lets unprivileged users run Docker containers without Docker installed. But it has no `docker-compose` — you have to manage each container manually, rewrite service hostnames, and wire everything up by hand.

**udocker-compose** adds compose-style orchestration so you can use existing `docker-compose.yml` files with udocker directly.

<details>
<summary>中文</summary>

udocker 允许非特权用户在没有 Docker 的情况下运行容器。但它没有 `docker-compose` —— 你需要手动管理每个容器、重写服务主机名、手动串联所有配置。

**udocker-compose** 为 udocker 添加了编排功能，让你可以直接使用现有的 `docker-compose.yml` 文件。

</details>

## Features

- Parses `docker-compose.yml` (v2/v3 format) — use your existing compose files as-is
- Topological dependency resolution (`depends_on`)
- Service name resolution via `/etc/hosts` injection — no need to rewrite `postgres` to `127.0.0.1` in connection strings
- Named volume management (mapped to local directories)
- Background/foreground execution with log management
- Auto-restart supervision (`restart: always/unless-stopped`)
- Health checks
- Single-file, zero-dependency (only requires Python 3 + PyYAML)

> **Note:** udocker runs all containers directly on the host network — there is **no network isolation** between containers. The `/etc/hosts` injection is purely a convenience feature that maps service names (like `postgres`, `redis`) to `127.0.0.1`, so your compose files work without modification. It does not provide any form of network isolation or virtual networking.

<details>
<summary>中文</summary>

- 解析 `docker-compose.yml`（v2/v3 格式）—— 直接使用现有的 compose 文件
- 基于拓扑排序的依赖解析（`depends_on`）
- 通过 `/etc/hosts` 注入实现服务名解析 —— 无需把连接串中的 `postgres` 改为 `127.0.0.1`
- 命名卷管理（映射为本地目录）
- 后台/前台运行与日志管理
- 自动重启监控（`restart: always/unless-stopped`）
- 健康检查
- 单文件，仅依赖 Python 3 + PyYAML

> **注意：** udocker 的所有容器直接运行在宿主机网络上，**没有任何网络隔离**。`/etc/hosts` 注入只是一个便利功能，将服务名（如 `postgres`、`redis`）映射到 `127.0.0.1`，让你的 compose 文件无需修改即可使用。它不提供任何形式的网络隔离或虚拟网络。

</details>

## Quick Start

### Installation

```bash
# 1. Install udocker (if not already installed)
pip install udocker
udocker install

# 2. Install udocker-compose
git clone https://github.com/apnn633/udocker-compose.git
chmod +x udocker-compose/udocker-compose
ln -s $(pwd)/udocker-compose/udocker-compose ~/.local/bin/udocker-compose

# 3. Install dependency
pip install pyyaml
```

### Usage

```bash
cd your-project/   # directory containing docker-compose.yml

udocker-compose up -d          # Start all services in background
udocker-compose ps             # Show service status
udocker-compose logs -f        # Follow logs
udocker-compose stop           # Stop services (keep containers)
udocker-compose down           # Stop and remove containers
udocker-compose down -v        # Also remove named volumes
```

## Commands

| Command | Description |
|---------|-------------|
| `up [-d] [service...]` | Create and start services. `-d` for background |
| `down [-v]` | Stop and remove containers. `-v` removes volumes |
| `ps [service...]` | List service status |
| `pull [service...]` | Pull service images |
| `logs [-f] [-n N] [service...]` | View logs. `-f` to follow |
| `restart [service...]` | Restart services |
| `stop [service...]` | Stop services without removing |
| `start [service...]` | Start stopped services |
| `exec <service> <cmd>` | Execute command in service container |
| `run [--rm] <service> <cmd>` | Run a one-off command |
| `config` | Validate and display parsed configuration |

<details>
<summary>中文</summary>

| 命令 | 说明 |
|------|------|
| `up [-d] [service...]` | 创建并启动服务，`-d` 后台运行 |
| `down [-v]` | 停止并删除容器，`-v` 同时删除卷 |
| `ps [service...]` | 列出服务状态 |
| `pull [service...]` | 拉取镜像 |
| `logs [-f] [-n N] [service...]` | 查看日志，`-f` 实时跟踪 |
| `restart [service...]` | 重启服务 |
| `stop [service...]` | 停止服务（保留容器） |
| `start [service...]` | 启动已停止的服务 |
| `exec <service> <cmd>` | 在容器中执行命令 |
| `run [--rm] <service> <cmd>` | 运行一次性命令 |
| `config` | 显示解析后的配置 |

</details>

## Service Name Resolution

In Docker Compose, containers on the same network can reach each other by service name (e.g., `postgres:5432`). This works because Docker creates virtual networks with built-in DNS.

udocker has **no network isolation** — all containers run directly on the host network stack, sharing the same ports and IP. There are no virtual networks, no per-container IPs, and no DNS.

To let you use existing `docker-compose.yml` files **without rewriting connection strings**, udocker-compose injects an `/etc/hosts` file into each container that maps all service names to `127.0.0.1`:

```
# Auto-generated /etc/hosts inside each container:
127.0.0.1   localhost
127.0.0.1   new-api   postgres   redis
```

So `postgresql://user:pass@postgres:5432/db` just works — `postgres` resolves to `127.0.0.1`, where the postgres process is already listening. **This is not networking — it's just hostname aliasing for convenience.**

### What this does NOT provide

- No network isolation — every service is reachable from the host and from each other
- No per-container IP addresses
- No virtual networks or bridge interfaces
- Two services cannot bind the same port (they share the host's port space)
- Ports below 1024 still require root

<details>
<summary>中文</summary>

在 Docker Compose 中，同一网络下的容器可以通过服务名互相访问（如 `postgres:5432`），因为 Docker 创建了带有内置 DNS 的虚拟网络。

udocker **没有网络隔离** —— 所有容器直接运行在宿主机网络栈上，共享端口和 IP。没有虚拟网络，没有容器独立 IP，没有 DNS。

为了让你**不用修改连接串**就能使用现有的 `docker-compose.yml`，udocker-compose 会注入一个 `/etc/hosts` 文件到每个容器中，将所有服务名映射到 `127.0.0.1`。

所以 `postgresql://user:pass@postgres:5432/db` 直接就能用 —— `postgres` 解析为 `127.0.0.1`，而 postgres 进程确实在那个地址监听。**这不是网络功能，只是主机名别名的便利映射。**

### 不提供的功能

- 无网络隔离 —— 所有服务对宿主机和彼此都可见
- 无容器独立 IP
- 无虚拟网络或桥接接口
- 两个服务不能绑定同一端口（共享宿主机端口空间）
- 1024 以下端口仍需 root

</details>

## Example: Multi-Service Application

Given this `docker-compose.yml`:

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

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `UDOCKER_COMPOSE_UDOCKER` | `udocker` | Path to udocker binary |
| `UDOCKER_COMPOSE_EXECMODE` | `P1` | Execution mode (P1, P2, F1-F4, R1-R3, S1) |
| `UDOCKER_COMPOSE_DEBUG` | unset | Set to `1` for debug output |

### Execution Modes

udocker supports multiple execution backends. Choose based on your environment:

| Mode | Engine | Performance | Best For |
|------|--------|-------------|----------|
| **P1** (default) | PRoot + seccomp | Medium | General use, Termux/Android |
| **P2** | PRoot (no accel) | Low | Fallback when P1 fails |
| **F1-F4** | Fakechroot | High | Performance-sensitive (not Termux) |
| **R1-R3** | runc/crun | High | Systems with user namespace support |
| **S1** | Singularity | High | HPC clusters |

```bash
# Change execution mode
UDOCKER_COMPOSE_EXECMODE=F1 udocker-compose up -d
```

<details>
<summary>中文 - 配置说明</summary>

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `UDOCKER_COMPOSE_UDOCKER` | `udocker` | udocker 可执行文件路径 |
| `UDOCKER_COMPOSE_EXECMODE` | `P1` | 执行模式 |
| `UDOCKER_COMPOSE_DEBUG` | 未设置 | 设为 `1` 启用调试输出 |

### 执行模式

| 模式 | 引擎 | 性能 | 适用场景 |
|------|------|------|----------|
| **P1**（默认） | PRoot + seccomp | 中 | 通用，Termux/Android |
| **P2** | PRoot 无加速 | 低 | P1 不可用时的后备 |
| **F1-F4** | Fakechroot | 高 | 性能敏感（不支持 Termux） |
| **R1-R3** | runc/crun | 高 | 支持 user namespace 的系统 |
| **S1** | Singularity | 高 | HPC 集群 |

</details>

### Compose File Support

Supported `docker-compose.yml` features:

| Feature | Status | Notes |
|---------|--------|-------|
| `image` | Supported | |
| `build` | Not supported | Build elsewhere, use `udocker load` |
| `command` | Supported | |
| `entrypoint` | Supported | |
| `environment` | Supported | dict and list format |
| `env_file` | Supported | |
| `volumes` (bind) | Supported | Relative paths resolved |
| `volumes` (named) | Supported | Stored in `.udocker-compose/volumes/` |
| `ports` | Supported | Pn mode only, host network |
| `depends_on` | Supported | Topological sort |
| `restart` | Supported | `always`, `unless-stopped` |
| `healthcheck` | Supported | CMD, CMD-SHELL |
| `networks` | Partial | No isolation; service names mapped to `127.0.0.1` via `/etc/hosts` |
| `container_name` | Supported | |
| `hostname` | Supported | Via env var |
| `working_dir` | Supported | |
| `user` | Supported | |
| `devices` | Partial | Rn mode only |
| `shm_size` | Not supported | |
| `privileged` | Not supported | No real root |
| `cap_add` | Not supported | |

## Comparison with Docker Compose

| Aspect | Docker Compose | udocker-compose |
|--------|---------------|-----------------|
| Root required | Yes (or docker group) | No |
| Daemon | Requires dockerd | No daemon |
| Network isolation | Full (veth + bridge) | **None** — all services share host network |
| Port mapping | iptables NAT | No mapping needed — ports bind directly on host |
| Image building | `docker build` | Not supported |
| Named volumes | Managed by Docker | Local directories |
| Restart policy | dockerd supervises | Background thread |
| Service scaling | `--scale` | Not supported |
| Compose profiles | Supported | Not supported |

<details>
<summary>中文 - 与 Docker Compose 对比</summary>

| 方面 | Docker Compose | udocker-compose |
|------|---------------|-----------------|
| 需要 root | 是（或 docker 组） | 不需要 |
| 守护进程 | 需要 dockerd | 无守护进程 |
| 网络隔离 | 完整（veth + bridge） | **无** —— 所有服务共享宿主机网络 |
| 端口映射 | iptables NAT | 不需要映射，端口直接绑定在宿主机上 |
| 镜像构建 | `docker build` | 不支持 |
| 命名卷 | Docker 管理 | 本地目录 |
| 重启策略 | dockerd 监控 | 后台线程 |
| 服务扩展 | `--scale` | 不支持 |

</details>

## State Directory

udocker-compose stores runtime state in `.udocker-compose/` within the project directory:

```
.udocker-compose/
  ├── state.json          # Service state tracking
  ├── pids/               # PID files for running services
  │   ├── redis.pid
  │   └── postgres.pid
  ├── logs/               # Service stdout/stderr logs
  │   ├── redis.log
  │   └── postgres.log
  ├── network/
  │   └── hosts           # Generated /etc/hosts file
  └── volumes/
      └── pg_data/        # Named volume data
```

## Platform Notes

### Termux / Android

- Only Pn modes work (P1 recommended)
- Set `UDOCKER_USE_PROOT_EXECUTABLE=$(which proot)` if using Termux's proot
- No user namespace support — all containers share host network, no isolation

### HPC / Compute Clusters

- All modes available depending on cluster configuration
- Designed for batch job environments
- MPI integration possible via udocker

<details>
<summary>中文 - 平台说明</summary>

### Termux / Android

- 仅 Pn 模式可用（推荐 P1）
- 使用 Termux 的 proot 时设置 `UDOCKER_USE_PROOT_EXECUTABLE=$(which proot)`
- 无 user namespace 支持，所有容器共享宿主机网络，无隔离

### HPC / 计算集群

- 所有模式可用（取决于集群配置）
- 专为批处理作业环境设计
- 可通过 udocker 进行 MPI 集成

</details>

## Requirements

- Python >= 3.7
- [PyYAML](https://pypi.org/project/PyYAML/)
- [udocker](https://github.com/indigo-dc/udocker) >= 1.3.0

## License

MIT
