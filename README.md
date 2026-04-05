# udocker-compose

Docker Compose compatible orchestration tool for [udocker](https://github.com/indigo-dc/udocker) — run multi-container applications **without root privileges**.

## Why?

udocker lets unprivileged users run Docker containers without Docker installed. But it lacks two key features:

1. **No `docker-compose`** — you have to manage each container manually
2. **No container networking** — services can't discover each other by name

**udocker-compose** fills both gaps. It parses standard `docker-compose.yml` files and orchestrates udocker containers with simulated networking via `/etc/hosts` injection.

## Features

- Parses `docker-compose.yml` (v2/v3 format)
- Topological dependency resolution (`depends_on`)
- Simulated Docker networking (service name DNS via `/etc/hosts`)
- Named volume management (mapped to local directories)
- Background/foreground execution with log management
- Auto-restart supervision (`restart: always/unless-stopped`)
- Health checks
- Single-file, zero-dependency (only requires Python 3 + PyYAML)

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

## How Networking Works

Docker creates isolated virtual networks where containers get their own IPs and discover each other by service name. udocker cannot do this (no root = no network namespaces).

**udocker-compose** simulates this by:

1. Generating an `/etc/hosts` file mapping all service names to `127.0.0.1`
2. Bind-mounting this file into every container
3. Injecting it into the container rootfs as a fallback

```
# Auto-generated /etc/hosts inside each container:
127.0.0.1   localhost
127.0.0.1   new-api   postgres   redis
```

This means connection strings like `postgresql://user:pass@postgres:5432/db` work **without modification** — `postgres` resolves to `127.0.0.1`, where the postgres service is actually listening.

### Networking Limitations

- All services share the host network stack — no isolation
- Two services cannot bind the same port (workaround: change one via config/command)
- Ports below 1024 require root
- No virtual network creation (`docker network` equivalent)

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
| `networks` | Simulated | `/etc/hosts` injection |
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
| Network isolation | Full (veth + bridge) | Simulated (/etc/hosts) |
| Port mapping | iptables NAT | Direct host binding |
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
- No user namespace support — networking is host-only

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
