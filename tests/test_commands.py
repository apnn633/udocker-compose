import importlib.machinery
import importlib.util
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "udocker-compose"
LOADER = importlib.machinery.SourceFileLoader("udocker_compose", str(SCRIPT_PATH))
SPEC = importlib.util.spec_from_loader("udocker_compose", LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(MODULE)

UdockerCompose = MODULE.UdockerCompose


class CommandsTest(unittest.TestCase):
    def write_compose(self, content: str) -> Path:
        tmpdir = Path(tempfile.mkdtemp())
        compose_file = tmpdir / "docker-compose.yml"
        compose_file.write_text(textwrap.dedent(content))
        return compose_file

    def test_cp_from_container_to_host(self):
        tmpdir = Path(tempfile.mkdtemp())
        compose_file = tmpdir / "docker-compose.yml"
        compose_file.write_text(textwrap.dedent(
            """
            services:
              app:
                image: demo:latest
            """
        ))
        uc = UdockerCompose(compose_files=[compose_file])

        # Create a fake container rootfs
        rootfs = tmpdir / "rootfs"
        (rootfs / "etc").mkdir(parents=True)
        (rootfs / "etc" / "hosts").write_text("127.0.0.1 localhost\n")

        def fake_udocker(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = str(rootfs)
            return Result()

        with patch.object(MODULE, "udocker", side_effect=fake_udocker):
            dest = tmpdir / "hosts.copy"
            uc.cmd_cp("app:/etc/hosts", str(dest))
            self.assertTrue(dest.exists())
            self.assertIn("localhost", dest.read_text())

    def test_cp_from_host_to_container(self):
        tmpdir = Path(tempfile.mkdtemp())
        compose_file = tmpdir / "docker-compose.yml"
        compose_file.write_text(textwrap.dedent(
            """
            services:
              app:
                image: demo:latest
            """
        ))
        uc = UdockerCompose(compose_files=[compose_file])

        rootfs = tmpdir / "rootfs"
        (rootfs / "data").mkdir(parents=True)
        src = tmpdir / "hello.txt"
        src.write_text("hello")

        def fake_udocker(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = str(rootfs)
            return Result()

        with patch.object(MODULE, "udocker", side_effect=fake_udocker):
            uc.cmd_cp(str(src), "app:/data/hello.txt")
            copied = rootfs / "data" / "hello.txt"
            self.assertTrue(copied.exists())
            self.assertEqual(copied.read_text(), "hello")

    def test_create_command_creates_state_without_starting(self):
        tmpdir = Path(tempfile.mkdtemp())
        compose_file = tmpdir / "docker-compose.yml"
        compose_file.write_text(textwrap.dedent(
            """
            services:
                app:
                    image: demo:latest
            """
        ))
        uc = UdockerCompose(compose_files=[compose_file])
        calls = []

        def fake_udocker(*args, **kwargs):
            calls.append(args)
            class Result:
                returncode = 0
                stdout = ""
            # Simulate inspect failing so create proceeds
            if args and args[0] == "inspect":
                Result.returncode = 1
            return Result()

        with patch.object(MODULE, "udocker", side_effect=fake_udocker):
            uc.cmd_create()
        self.assertTrue(any(a and a[0] == "create" for a in calls))
        self.assertEqual(uc.state.get_service_state("app").get("status"), "created")

    def test_rm_command_removes_container_state(self):
        tmpdir = Path(tempfile.mkdtemp())
        compose_file = tmpdir / "docker-compose.yml"
        compose_file.write_text(textwrap.dedent(
            """
            services:
                app:
                    image: demo:latest
            """
        ))
        uc = UdockerCompose(compose_files=[compose_file])
        uc.state.init()
        uc.state.set_service_state("app", created=True)

        def fake_udocker(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = ""
            return Result()

        with patch.object(MODULE, "udocker", side_effect=fake_udocker):
            uc.cmd_rm(services=["app"], force=True)
        self.assertIsNone(uc.state.get_service_state("app").get("created"))


if __name__ == "__main__":
    unittest.main()
