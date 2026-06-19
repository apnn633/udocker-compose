import importlib.machinery
import importlib.util
import os
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "udocker-compose"
LOADER = importlib.machinery.SourceFileLoader("udocker_compose", str(SCRIPT_PATH))
SPEC = importlib.util.spec_from_loader("udocker_compose", LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(MODULE)
ComposeConfig = MODULE.ComposeConfig


class ComposeConfigTest(unittest.TestCase):
    def write_compose(self, content: str) -> Path:
        tmpdir = Path(tempfile.mkdtemp())
        compose_file = tmpdir / "docker-compose.yml"
        compose_file.write_text(textwrap.dedent(content))
        return compose_file

    def test_environment_ports_and_volumes_are_normalized(self):
        compose_file = self.write_compose(
            """
            services:
              app:
                image: demo:latest
                environment:
                  - APP_MODE=prod
                  - EMPTY_FROM_ENV
                ports:
                  - "127.0.0.1:8080:80/tcp"
                  - 9000
                volumes:
                  - data:/var/lib/data
                  - ./cache:/cache:ro
            volumes:
              data: {}
            """
        )

        config = ComposeConfig(compose_file)
        service = config.services["app"]

        self.assertEqual(service["environment"]["APP_MODE"], "prod")
        self.assertIn("EMPTY_FROM_ENV", service["environment"])
        self.assertEqual(
            service["ports"],
            [
                {"host": "8080", "container": "80", "protocol": "tcp"},
                {"host": "9000", "container": "9000", "protocol": "tcp"},
            ],
        )
        self.assertEqual(
            service["volumes"],
            [
                {"host": "data", "container": "/var/lib/data", "mode": "rw"},
                {"host": "./cache", "container": "/cache", "mode": "ro"},
            ],
        )

    def test_depends_on_is_returned_in_topological_order(self):
        compose_file = self.write_compose(
            """
            services:
              app:
                image: app:latest
                depends_on:
                  - redis
                  - db
              redis:
                image: redis:latest
              db:
                image: postgres:latest
            """
        )

        config = ComposeConfig(compose_file)
        self.assertEqual(config.get_startup_order(), ["db", "redis", "app"])

    def test_env_interpolation(self):
        compose_file = self.write_compose(
            """
            services:
              app:
                image: demo:${TAG:-latest}
                environment:
                  - MODE=${MODE}
                  - STATIC=value
            """
        )
        os.environ["MODE"] = "prod"
        try:
            config = ComposeConfig(compose_file)
            self.assertEqual(config.services["app"]["image"], "demo:latest")
            self.assertEqual(config.services["app"]["environment"]["MODE"], "prod")
            self.assertEqual(config.services["app"]["environment"]["STATIC"], "value")
        finally:
            os.environ.pop("MODE", None)

    def test_port_range_expansion(self):
        compose_file = self.write_compose(
            """
            services:
              app:
                image: demo:latest
                ports:
                  - "8000-8002:9000-9002"
            """
        )

        config = ComposeConfig(compose_file)
        self.assertEqual(
            config.services["app"]["ports"],
            [
                {"host": "8000", "container": "9000", "protocol": "tcp"},
                {"host": "8001", "container": "9001", "protocol": "tcp"},
                {"host": "8002", "container": "9002", "protocol": "tcp"},
            ],
        )


    def test_profiles_filter_services(self):
        compose_file = self.write_compose(
            """
            services:
              web:
                image: web:latest
              worker:
                image: worker:latest
                profiles:
                  - batch
            """
        )
        config_default = ComposeConfig(compose_file)
        self.assertIn("web", config_default.services)
        self.assertNotIn("worker", config_default.services)

        config_batch = ComposeConfig(compose_file, profiles={"batch"})
        self.assertIn("web", config_batch.services)
        self.assertIn("worker", config_batch.services)

    def test_multiple_compose_files_are_merged(self):
        tmpdir = Path(tempfile.mkdtemp())
        base = tmpdir / "docker-compose.yml"
        override = tmpdir / "docker-compose.override.yml"
        base.write_text(textwrap.dedent(
            """
            services:
              app:
                image: demo:latest
                environment:
                  A: base
            """
        ))
        override.write_text(textwrap.dedent(
            """
            services:
              app:
                environment:
                  B: override
            """
        ))
        config = ComposeConfig([base, override])
        self.assertEqual(config.services["app"]["environment"]["A"], "base")
        self.assertEqual(config.services["app"]["environment"]["B"], "override")

    def test_labels_and_stop_options_are_normalized(self):
        compose_file = self.write_compose(
            """
            services:
              app:
                image: demo:latest
                labels:
                  - com.example.key=value
                  - bare-label
                stop_signal: SIGINT
                stop_grace_period: 30s
            """
        )
        config = ComposeConfig(compose_file)
        service = config.services["app"]
        self.assertEqual(service["labels"]["com.example.key"], "value")
        self.assertEqual(service["labels"]["bare-label"], "")
        self.assertEqual(service["stop_signal"], "SIGINT")
        self.assertEqual(service["stop_grace_period"], 30.0)

    def test_secrets_and_configs_are_normalized(self):
        compose_file = self.write_compose(
            """
            services:
              app:
                image: demo:latest
                secrets:
                  - my_secret
                  - source: other_secret
                    target: /etc/other
                configs:
                  - my_config
            secrets:
              my_secret:
                file: ./secrets/my_secret.txt
              other_secret:
                environment: OTHER_SECRET
            configs:
              my_config:
                file: ./configs/my_config.txt
            """
        )
        config = ComposeConfig(compose_file)
        service = config.services["app"]
        self.assertEqual(service["secrets"][0]["name"], "my_secret")
        self.assertEqual(service["secrets"][1]["target"], "/etc/other")
        self.assertEqual(service["configs"][0]["name"], "my_config")

    def test_env_file_from_cli_is_loaded(self):
        tmpdir = Path(tempfile.mkdtemp())
        compose_file = tmpdir / "docker-compose.yml"
        env_file = tmpdir / "custom.env"
        compose_file.write_text(textwrap.dedent(
            """
            services:
              app:
                image: demo:${TAG}
            """
        ))
        env_file.write_text("TAG=v1\n")
        config = ComposeConfig(compose_file, env_overrides=[env_file])
        self.assertEqual(config.services["app"]["image"], "demo:v1")

    def test_depends_on_conditions_are_normalized(self):
        compose_file = self.write_compose(
            """
            services:
              app:
                image: app:latest
                depends_on:
                  db:
                    condition: service_healthy
                  cache:
                    condition: service_started
              db:
                image: postgres:latest
              cache:
                image: redis:latest
            """
        )
        config = ComposeConfig(compose_file)
        app_deps = config.services["app"]["depends_on"]
        self.assertEqual(app_deps, [
            {"name": "db", "condition": "service_healthy"},
            {"name": "cache", "condition": "service_started"},
        ])
        self.assertEqual(config.get_depends_on_names("app"), ["db", "cache"])

    def test_additional_service_fields_are_normalized(self):
        compose_file = self.write_compose(
            """
            services:
              app:
                image: demo:latest
                domainname: example.com
                stdin_open: true
                tty: true
                read_only: true
                cap_drop:
                  - ALL
                group_add:
                  - 1000
                init: true
                ulimits:
                  nofile:
                    soft: 1000
                    hard: 2000
                logging:
                  driver: json-file
                network_mode: host
                platform: linux/amd64
                runtime: runc
                external_links:
                  - legacy_db:db
            """
        )
        config = ComposeConfig(compose_file)
        svc = config.services["app"]
        self.assertEqual(svc["domainname"], "example.com")
        self.assertTrue(svc["stdin_open"])
        self.assertTrue(svc["tty"])
        self.assertTrue(svc["read_only"])
        self.assertEqual(svc["cap_drop"], ["ALL"])
        self.assertEqual(svc["group_add"], [1000])
        self.assertTrue(svc["init"])
        self.assertEqual(svc["ulimits"]["nofile"]["soft"], 1000)
        self.assertEqual(svc["logging"]["driver"], "json-file")
        self.assertEqual(svc["network_mode"], "host")
        self.assertEqual(svc["platform"], "linux/amd64")
        self.assertEqual(svc["runtime"], "runc")
        self.assertEqual(svc["external_links"], ["legacy_db:db"])

    def test_project_directory_overrides_base_path(self):
        tmpdir = Path(tempfile.mkdtemp())
        compose_file = tmpdir / "docker-compose.yml"
        compose_file.write_text(textwrap.dedent(
            """
            services:
              app:
                image: demo:latest
            """
        ))
        config = ComposeConfig(compose_file, project_directory=tmpdir)
        self.assertEqual(config.project_dir, tmpdir.resolve())


if __name__ == "__main__":
    unittest.main()
