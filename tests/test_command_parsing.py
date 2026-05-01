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
ServiceManager = MODULE.ServiceManager


class DummyState:
    def get_hosts_file(self):
        return Path(tempfile.mkdtemp()) / "hosts"


class DummyNetwork:
    def get_run_args(self):
        return []


class DummyVolumes:
    def get_run_args(self, service_name):
        return []


class CommandParsingTest(unittest.TestCase):
    def write_compose(self, content: str) -> Path:
        tmpdir = Path(tempfile.mkdtemp())
        compose_file = tmpdir / "docker-compose.yml"
        compose_file.write_text(textwrap.dedent(content))
        return compose_file

    def test_string_command_preserves_quoted_segments(self):
        compose_file = self.write_compose(
            """
            services:
              app:
                image: demo:latest
                command: python -c "print('hello world')"
            """
        )

        config = ComposeConfig(compose_file)
        manager = ServiceManager(config, DummyState(), DummyNetwork(), DummyVolumes())
        self.assertEqual(
            manager._get_service_command("app"),
            ["python", "-c", "print('hello world')"],
        )

    def test_string_entrypoint_preserves_quoted_segments(self):
        compose_file = self.write_compose(
            """
            services:
              app:
                image: demo:latest
                entrypoint: sh -lc "echo hello world"
            """
        )

        config = ComposeConfig(compose_file)
        manager = ServiceManager(config, DummyState(), DummyNetwork(), DummyVolumes())
        run_args = manager._build_run_args("app")
        self.assertEqual(run_args[run_args.index("--entrypoint") + 1], "sh")
        self.assertEqual(manager._get_service_command("app"), ["-lc", "echo hello world"])

    def test_empty_string_entrypoint_clears_image_entrypoint(self):
        compose_file = self.write_compose(
            """
            services:
              app:
                image: demo:latest
                entrypoint: ""
                command: echo hello
            """
        )

        config = ComposeConfig(compose_file)
        manager = ServiceManager(config, DummyState(), DummyNetwork(), DummyVolumes())
        run_args = manager._build_run_args("app")
        self.assertEqual(run_args[run_args.index("--entrypoint") + 1], "")
        self.assertEqual(manager._get_service_command("app"), ["echo", "hello"])


if __name__ == "__main__":
    unittest.main()
