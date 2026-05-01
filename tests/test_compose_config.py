import importlib.machinery
import importlib.util
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


if __name__ == "__main__":
    unittest.main()
