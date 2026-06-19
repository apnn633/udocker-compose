# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository is a single-file Python CLI named `udocker-compose` that provides Docker Compose-style orchestration on top of `udocker`.

Key constraints from the code and README:
- Containers run on the host network; there is no Docker-style network isolation.
- Service-to-service name resolution is simulated by generating an `/etc/hosts` file that maps service names to `127.0.0.1`.
- `build` is parsed for compatibility but not actually supported by execution.
- Runtime state is stored per target project in a `.udocker-compose/` directory next to the compose file being operated on.

## Common commands

## Dependencies

Install the only Python dependency used by the script:

```bash
python3 -m pip install pyyaml
```

`udocker` must also be installed and available on `PATH`, unless `UDOCKER_COMPOSE_UDOCKER` points to it explicitly.

## CLI usage during development

Show help:

```bash
python3 ./udocker-compose --help
```

Validate Python syntax:

```bash
python3 -m py_compile ./udocker-compose
```

Validate and inspect a compose file:

```bash
python3 ./udocker-compose -f /path/to/docker-compose.yml config
```

Start all services for a compose project:

```bash
python3 ./udocker-compose -f /path/to/docker-compose.yml up -d
```

Start only one service plus its dependencies:

```bash
python3 ./udocker-compose -f /path/to/docker-compose.yml up SERVICE_NAME
```

View status:

```bash
python3 ./udocker-compose -f /path/to/docker-compose.yml ps
```

Follow logs:

```bash
python3 ./udocker-compose -f /path/to/docker-compose.yml logs -f
```

Stop and remove services:

```bash
python3 ./udocker-compose -f /path/to/docker-compose.yml down
```

Stop and remove services plus named volumes:

```bash
python3 ./udocker-compose -f /path/to/docker-compose.yml down -v
```

Run a one-off command in a service container:

```bash
python3 ./udocker-compose -f /path/to/docker-compose.yml run --rm SERVICE_NAME COMMAND [ARGS...]
```

Execute a command in an existing service container:

```bash
python3 ./udocker-compose -f /path/to/docker-compose.yml exec SERVICE_NAME COMMAND [ARGS...]
```

## Testing / validation

The repository now has a small automated test suite focused on compose parsing, normalization, command tokenization, CLI flags, and color output behavior.

Use these commands for validation:
- `python3 -m py_compile ./udocker-compose` for syntax checking
- `python3 -m unittest tests.test_compose_config tests.test_command_parsing tests.test_cli -v` for automated regression coverage
- `python3 ./udocker-compose --help` for parser/entrypoint validation
- `python3 ./udocker-compose --version` for version output validation
- `python3 ./udocker-compose -f /path/to/docker-compose.yml config` to verify compose parsing, variable interpolation, and startup order
- `python3 ./udocker-compose -f /path/to/docker-compose.yml up SERVICE_NAME` when validating behavior for a single service path

If you add more tests later, keep this section updated with the exact commands for running the full suite and targeted subsets.

## Environment variables

The CLI behavior is controlled by these environment variables:

```bash
UDOCKER_COMPOSE_UDOCKER   # path to the udocker binary, default: udocker
UDOCKER_COMPOSE_EXECMODE  # udocker exec mode, default: P1
UDOCKER_COMPOSE_DEBUG=1   # enable debug logging
NO_COLOR=1                # disable ANSI color output
```

## High-level architecture

The entire implementation lives in `udocker-compose`. The code is organized as a small set of cooperating classes rather than multiple modules.

### 1. Compose parsing and normalization

`ComposeConfig`:
- locates and loads one compose file
- loads a project-local `.env` file and interpolates `${VAR}` / `${VAR:-default}` / `$VAR` placeholders
- normalizes service definitions into a predictable internal structure
- resolves `environment`, `env_file`, `ports` (including ranges), `volumes`, `depends_on`, and service naming
- computes startup order with a topological sort based on `depends_on`

This class is the source of truth for feature support and compatibility behavior.

### 2. Per-project runtime state

`StateManager` manages the `.udocker-compose/` directory created inside the target compose project directory. It persists:
- `state.json` with service metadata/status and last recorded exit codes
- `pids/` for background process tracking
- `logs/` for captured stdout/stderr
- `network/hosts` for generated host aliases
- `volumes/` for named-volume backing directories
- `compose.pid` for the daemonized `up -d` process

State file access is protected by a thread lock because the restart supervisor runs in a background thread. When debugging lifecycle issues, inspect this directory first.

### 3. Simulated networking

`NetworkManager` implements the core compatibility trick for Compose service discovery:
- generate a shared hosts file containing every service name, container name, and configured hostname
- map all of them to `127.0.0.1`
- mount or inject that file into each container as `/etc/hosts`

This is why existing compose connection strings like `postgres:5432` can work even though all services actually share the host network.

### 4. Volume handling

`VolumeManager` translates compose volume declarations into paths usable by `udocker`:
- named volumes become subdirectories in `.udocker-compose/volumes/`
- relative bind mounts are resolved relative to the compose project directory
- missing host directories are created on demand before running containers

### 5. Service lifecycle and command translation

`ServiceManager` is the main execution layer. It translates normalized service config into `udocker` commands for:
- `pull`
- `create`
- `run`/start
- `stop`
- `remove`
- one-off execution and health checks

Important implementation detail: background services are not managed by a daemon. They are launched as local subprocesses, tracked by PID files, and their output is appended to per-service log files.

### 6. Restart supervision

`RestartSupervisor` is an in-process background thread that periodically checks tracked PIDs and restarts services whose policy is `always`, `unless-stopped`, or `on-failure`.

In foreground `up` mode, the supervisor lives inside the running `udocker-compose` process. In `up -d` mode, the CLI daemonizes into a background process (stored in `.udocker-compose/compose.pid`) so the supervisor and restart policies remain active after the shell prompt returns. Use `down` to stop the daemon.

### 7. Top-level orchestration

`UdockerCompose` wires the managers together and implements subcommands (`up`, `down`, `ps`, `pull`, `logs`, `restart`, `stop`, `start`, `exec`, `run`, `config`).

The most important orchestration flow is `cmd_up`:
1. initialize state directories
2. generate the shared hosts file
3. create named-volume directories
4. compute dependency order and expand requested services to include dependencies
5. create containers
6. inject hosts data
7. start processes and optionally start the restart supervisor

## Important behavioral constraints

- `build` is not supported at runtime; the script warns and expects images to be built elsewhere and imported into `udocker`.
- Port publishing is only added for `P*` exec modes. Port ranges are expanded into individual mappings.
- Device mapping is only added for `R*` exec modes.
- Host IP in `host_ip:host_port:container_port` port syntax is parsed but ignored; only host/container ports are used.
- Command strings are tokenized with `shlex.split()`, so quoted string-form commands are preserved more accurately than a plain whitespace split. YAML list form is still the most exact representation.
- Named volume detection is heuristic: non-absolute, non-relative, non-tilde mount sources are treated as candidate named volumes.
- `shm_size`, `privileged`, `cap_add`, `tmpfs`, and `dns` are parsed but not supported; a warning is emitted for each.
- `restart: on-failure` is supported by recording child exit codes when reaping exited processes.

## Files worth reading first

- `udocker-compose` — all CLI, orchestration, and runtime behavior
- `docs/README.md` — user-facing feature list, limitations, and supported compose semantics
