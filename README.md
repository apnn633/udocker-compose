# udocker-compose

Docker Compose compatible orchestration tool for [udocker](https://github.com/indigo-dc/udocker) — run multi-container applications **without root privileges**.

## Why?

udocker lets unprivileged users run Docker containers without Docker installed. But it has no `docker-compose` — you have to manage each container manually, rewrite service hostnames, and wire everything up by hand.

**udocker-compose** adds compose-style orchestration so you can use existing `docker-compose.yml` files with udocker directly.

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

## Requirements

- Python >= 3.7
- [PyYAML](https://pypi.org/project/PyYAML/)
- [udocker](https://github.com/indigo-dc/udocker) >= 1.3.0

## License

MIT
