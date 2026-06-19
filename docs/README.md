# udocker-compose

[English](./README.md) | [中文](./README.zh-CN.md)

Docker Compose-compatible orchestration for [udocker](https://github.com/indigo-dc/udocker) — run multi-container applications **without root privileges**.

## Why?

`udocker` lets unprivileged users run Docker containers without Docker installed. But it has no `docker-compose` — you have to manage each container manually, rewrite service hostnames, and wire everything up by hand.

**udocker-compose** adds compose-style orchestration so you can use existing `docker-compose.yml` files with `udocker` directly.

## Features

- Parses `docker-compose.yml` (v2/v3 format) — use your existing compose files as-is
- Supports **multiple compose files** (`-f base.yml -f override.yml`) and the `COMPOSE_FILE` environment variable
- Loads `.env` files, supports `--env-file`, and interpolates `${VAR}` / `${VAR:-default}` / `$VAR` placeholders
- **Profiles** support (`--profile` / `COMPOSE_PROFILES`)
- Topological dependency resolution (`depends_on`)
- Service name resolution via `/etc/hosts` injection — no need to rewrite `postgres` to `127.0.0.1` in connection strings
- Named volume management (mapped to local directories)
- Background/foreground execution with log management
- Auto-restart supervision (`restart: always/unless-stopped/on-failure`); `up -d` daemonizes so supervision persists after the shell returns
- Health checks
- Graceful stop using `stop_signal` and `stop_grace_period`
- Port range support (`8000-8010:8000-8010`)
- Secrets / configs mapped to bind mounts or environment variables
- `--no-deps` for `up` / `start`
- `--project-directory` and `--ansi` global options
- `cp`, `rm`, `create`, `pause`, `unpause`, `events` commands
- `depends_on` conditions (`service_healthy`)
- `--version` flag, `--ansi`, and `NO_COLOR` support
- Single-file, zero-dependency implementation apart from Python 3 + PyYAML

> **Note:** `udocker` runs all containers directly on the host network — there is **no network isolation** between containers. The `/etc/hosts` injection is purely a convenience feature that maps service names such as `postgres` and `redis` to `127.0.0.1`, so existing compose files work without modification. It does not provide virtual networking or isolation.
>
> Many advanced Docker Compose options (`cap_add`, `privileged`, `shm_size`, `ulimits`, `logging`, `network_mode`, `platform`, `runtime`, `init`, `dns`, `read_only`, etc.) are parsed for compatibility but cannot be enforced by udocker and are ignored with a warning.

## Quick Start

### Installation

**1. Install udocker**

Choose one of the following methods. The latest stable release is **1.3.17**.

```bash
# Option A: from the release tarball (recommended)
wget https://github.com/indigo-dc/udocker/releases/download/1.3.17/udocker-1.3.17.tar.gz
tar zxvf udocker-1.3.17.tar.gz
export PATH=$(pwd)/udocker-1.3.17/udocker:$PATH
udocker install

# Option B: from PyPI
pip install udocker
udocker install

# Option C: from the repository
git clone --depth=1 https://github.com/indigo-dc/udocker.git
(cd udocker/udocker && ln -s maincmd.py udocker)
export PATH=$(pwd)/udocker/udocker:$PATH
udocker install
```

**2. Install udocker-compose**

```bash
git clone https://github.com/apnn633/udocker-compose.git
chmod +x udocker-compose/udocker-compose
ln -s $(pwd)/udocker-compose/udocker-compose ~/.local/bin/udocker-compose
```

**3. Install dependency**

```bash
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
| `up [-d] [--no-deps] [--no-recreate] [--remove-orphans] [--abort-on-container-exit] [--exit-code-from] [service...]` | Create and start services |
| `down [-v] [--rmi] [service...]` | Stop and remove containers/volumes/images |
| `ps [service...]` | List service status |
| `pull [--ignore-pull-failures] [service...]` | Pull service images |
| `logs [-f] [-n N] [-t] [service...]` | View logs |
| `restart [service...]` | Restart services |
| `stop [service...]` | Stop services without removing containers |
| `start [--no-deps] [service...]` | Start stopped services |
| `exec <service> <cmd>` | Execute a command in a service container |
| `run [--rm] <service> <cmd>` | Run a one-off command |
| `kill [-s SIGNAL] [service...]` | Send a signal to running services |
| `top [service...]` | Show running processes |
| `images` | List images used by services |
| `port <service> [private_port]` | Show port mappings |
| `cp HOST_PATH SERVICE:PATH` | Copy files between host and container |
| `rm [-s] [-f] [-v] [service...]` | Remove stopped containers |
| `create [service...]` | Create containers without starting |
| `pause [service...]` | Pause services |
| `unpause [service...]` | Unpause services |
| `events [service...]` | Stream service state events |
| `config [--services] [--volumes]` | Validate and display parsed configuration |

## Service Name Resolution

In Docker Compose, containers on the same network can reach each other by service name such as `postgres:5432`. This works because Docker creates virtual networks with built-in DNS.

`udocker` has **no network isolation** — all containers run directly on the host network stack, sharing the same ports and IP. There are no virtual networks, no per-container IPs, and no DNS.

To let you use existing `docker-compose.yml` files **without rewriting connection strings**, `udocker-compose` injects an `/etc/hosts` file into each container that maps all service names to `127.0.0.1`:

```text
# Auto-generated /etc/hosts inside each container:
127.0.0.1   localhost
127.0.0.1   new-api   postgres   redis
```

So `postgresql://user:pass@postgres:5432/db` just works — `postgres` resolves to `127.0.0.1`, where the postgres process is already listening. **This is not networking — it is hostname aliasing for compatibility.**

### What this does NOT provide

- No network isolation — every service is reachable from the host and from each other
- No per-container IP addresses
- No virtual networks or bridge interfaces
- Two services cannot bind the same port because they share the host port space
- Ports below `1024` still require root privileges

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
| `UDOCKER_COMPOSE_UDOCKER` | `udocker` | Path to the `udocker` binary |
| `UDOCKER_COMPOSE_EXECMODE` | `P1` | Execution mode (`P1`, `P2`, `F1-F4`, `R1-R3`, `S1`) |
| `UDOCKER_COMPOSE_DEBUG` | unset | Set to `1` for debug output |
| `NO_COLOR` | unset | Set to `1`/`true`/`yes` to disable ANSI color output |
| `COMPOSE_FILE` | unset | Colon-separated list of compose files |
| `COMPOSE_PROFILES` | unset | Comma-separated list of enabled profiles |

### Execution Modes

`udocker` supports multiple execution backends. Choose based on your environment:

| Mode | Engine | Performance | Best For |
|------|--------|-------------|----------|
| **P1** (default) | PRoot PTRACE + seccomp | Medium | General use, Termux/Android |
| **P2** | PRoot PTRACE (no accel) | Low | Fallback when P1 fails |
| **F1-F4** | Fakechroot | High | Performance-sensitive workloads (glibc/musl; not Termux) |
| **R1** | runc/crun with user namespaces | High | Systems with unprivileged user namespaces |
| **R2** | runc/crun + P1 | High | Systems with user namespaces |
| **R3** | runc/crun + P2 | High | Systems with user namespaces, fallback |
| **S1** | Singularity | High | HPC clusters |

```bash
# Change execution mode
UDOCKER_COMPOSE_EXECMODE=F1 udocker-compose up -d
```

### Compose File Support

| Feature | Status | Notes |
|---------|--------|-------|
| `image` | Supported | |
| `build` | Not supported | Build elsewhere, then use `udocker load` |
| `command` | Supported | |
| `entrypoint` | Supported | |
| `environment` | Supported | Dict and list format |
| `env_file` | Supported | |
| `.env` file | Supported | Loaded from project directory |
| `volumes` (bind) | Supported | Relative paths resolved |
| `volumes` (named) | Supported | Stored in `.udocker-compose/volumes/` |
| `ports` | Supported | Pn mode only, host network; ranges expanded |
| `depends_on` | Supported | Topological sort |
| `restart` | Supported | `always`, `unless-stopped`, `on-failure` |
| `healthcheck` | Supported | `CMD`, `CMD-SHELL`; evaluated during `up` |
| `networks` | Partial | No isolation; service names map to `127.0.0.1` via `/etc/hosts` |
| `container_name` | Supported | |
| `hostname` | Supported | Via environment variable |
| `working_dir` | Supported | |
| `user` | Supported | |
| `devices` | Partial | Rn mode only |
| `shm_size` | Not supported | |
| `privileged` | Not supported | No real root |
| `cap_add` / `cap_drop` | Not supported | |
| `init` | Not supported | |
| `ulimits` | Not supported | |
| `logging` | Not supported | |
| `network_mode` | Not supported | |
| `platform` | Not supported | |
| `runtime` | Not supported | |
| `read_only` | Not supported | |
| `external_links` | Partial | Aliased to `127.0.0.1` in `/etc/hosts` |

## Comparison with Docker Compose

| Aspect | Docker Compose | udocker-compose |
|--------|---------------|-----------------|
| Root required | Yes (or docker group) | No |
| Daemon | Requires `dockerd` | No daemon |
| Network isolation | Full (veth + bridge) | **None** — all services share host network |
| Port mapping | iptables NAT | No mapping needed — ports bind directly on host |
| Image building | `docker build` | Not supported |
| Named volumes | Managed by Docker | Local directories |
| Restart policy | `dockerd` supervises | Background thread |
| Service scaling | `--scale` | Not supported |
| Compose profiles | Supported | Supported |
| depends_on conditions | `service_healthy` / `service_completed_successfully` | `service_healthy` supported; `service_completed_successfully` ignored |
| Copy files | `cp` | Supported via container rootfs |
| Pause/unpause | `pause` / `unpause` | Supported via SIGSTOP/SIGCONT |

## State Directory

`udocker-compose` stores runtime state in `.udocker-compose/` within the project directory:

```text
.udocker-compose/
  ├── state.json          # Service state tracking
  ├── compose.pid         # Daemonized up -d process
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

## Restart Behavior

`restart: always`, `restart: unless-stopped`, and `restart: on-failure` are implemented by a background supervisor thread.

- In foreground `up` mode, supervision lasts until you stop the CLI.
- In `up -d` mode, the CLI daemonizes into a background process and writes its PID to `.udocker-compose/compose.pid`, so supervision continues after the shell prompt returns.
- `down` stops the daemon (if running) and removes the services.

## Platform Notes

### Termux / Android

- Only Pn modes work (`P1` recommended)
- Set `UDOCKER_USE_PROOT_EXECUTABLE=$(which proot)` if using Termux's `proot`
- No user namespace support — all containers share the host network

### HPC / Compute Clusters

- All modes may be available depending on cluster configuration
- Designed for batch job environments
- MPI integration is possible via `udocker`

## Requirements

- Python >= 3.7
- [PyYAML](https://pypi.org/project/PyYAML/)
- [udocker](https://github.com/indigo-dc/udocker) >= 1.3.0 (tested with 1.3.17)

See the official udocker documentation for more details:

- [udocker documentation](https://indigo-dc.github.io/udocker/)
- [Installation manual](https://indigo-dc.github.io/udocker/installation_manual.html)
- [User manual](https://indigo-dc.github.io/udocker/user_manual.html)
- [Reference card](https://indigo-dc.github.io/udocker/reference_card.html)

## License

MIT
