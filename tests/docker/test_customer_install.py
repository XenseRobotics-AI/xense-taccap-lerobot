"""Exercise installer routing without sudo, network, Docker, or host changes."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = (ROOT / "docker/install_customer.sh").read_text().removesuffix('main "$@"\n')


class CustomerInstallTest(unittest.TestCase):
    def installer_env(self, **overrides):
        env = {key: value for key, value in os.environ.items() if not key.startswith(("XENSE_", "LEROBOT_IMAGE"))}
        return {**env, **overrides}

    def run_shell(self, body, mirror="cn"):
        with tempfile.TemporaryDirectory() as directory:
            return subprocess.run(
                ["bash", "-c", INSTALLER + '\nTEMP_DIR="$TEST_DIR"\n' + body],
                env=self.installer_env(TEST_DIR=directory, XENSE_MIRROR=mirror),
                capture_output=True,
                text=True,
            )

    def test_default_sources_and_host_apt_are_preserved(self):
        result = self.run_shell(
            """
configure_mirrors
printf '%s\\n' "$DOCKER_APT_URL" "$NVIDIA_APT_URL"
sudo() { printf '%s\\n' "$@"; }
apt_get update
test ! -e "$TEMP_DIR/sources.list.d"
""",
            mirror="default",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("https://download.docker.com", result.stdout)
        self.assertIn("https://nvidia.github.io/libnvidia-container", result.stdout)
        self.assertNotIn("Dir::Etc::", result.stdout)
        self.assertNotIn("mirrors.ustc.edu.cn", result.stdout)

    def test_unknown_mirror_stops_before_host_access(self):
        result = self.run_shell(
            """
require_normal_user() { echo UNEXPECTED_HOST_ACCESS; }
main
""",
            mirror="invalid",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown XENSE_MIRROR", result.stderr)
        self.assertNotIn("UNEXPECTED_HOST_ACCESS", result.stdout)

    def test_domestic_sources_and_apt_isolation(self):
        for distro, codename in [("ubuntu", "jammy"), ("debian", "bookworm")]:
            with self.subTest(distro=distro):
                result = self.run_shell(f"""
DISTRO_ID={distro}; DISTRO_CODENAME={codename}
configure_mirrors
cat "$TEMP_DIR/sources.list.d/system.list"
sudo() {{ printf '%s\\n' "$@"; }}
apt_get update
""")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"{codename}-security", result.stdout)
                self.assertIn("signed-by=/usr/share/keyrings/", result.stdout)
                self.assertIn("mirrors.ustc.edu.cn", result.stdout)
                self.assertIn("Dir::Etc::sourcelist=/dev/null", result.stdout)
                self.assertIn("Dir::Etc::sourceparts=", result.stdout)

    def test_vendor_sources_rewrite_upstream_urls(self):
        result = self.run_shell("""
DISTRO_ID=ubuntu; DISTRO_CODENAME=jammy
configure_mirrors
sudo() { :; }
gpg() { :; }
nvidia-smi() { echo 580.142; }
command() {
  if [[ "$*" == '-v nvidia-ctk' ]]; then return 1; fi
  builtin command "$@"
}
fetch_url() {
  printf 'FETCH %s\\n' "$1"
  printf 'deb https://nvidia.github.io/libnvidia-container/stable/deb/$(ARCH) /\\n' > "$2"
}
configure_docker_repository
install_nvidia_container_toolkit
cat "$TEMP_DIR/sources.list.d/docker.sources"
cat "$TEMP_DIR/sources.list.d/nvidia-container-toolkit.list"
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("https://mirrors.ustc.edu.cn/docker-ce/linux/ubuntu/gpg", result.stdout)
        self.assertIn("https://mirrors.ustc.edu.cn/libnvidia-container/gpgkey", result.stdout)
        self.assertIn("https://mirrors.ustc.edu.cn/libnvidia-container/stable/deb/$(ARCH)", result.stdout)
        self.assertNotIn("https://nvidia.github.io", result.stdout)
        self.assertNotIn("https://download.docker.com", result.stdout)

    def test_missing_archive_stops_before_host_install(self):
        result = self.run_shell("""
require_normal_user() { :; }
load_os_release() { :; }
resolve_image_ref() { :; }
detect_archive() { return 1; }
install_docker() { echo UNEXPECTED_INSTALL; }
main
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires a local image tar", result.stderr)
        self.assertNotIn("UNEXPECTED_INSTALL", result.stdout)

    def test_corrupt_archive_is_rejected(self):
        result = self.run_shell("""
ARCHIVE_PATH="$TEMP_DIR/image.tar"
printf original > "$ARCHIVE_PATH"
(cd "$TEMP_DIR"; sha256sum image.tar > SHA256SUMS)
printf corrupted > "$ARCHIVE_PATH"
verify_archive
echo UNEXPECTED_SUCCESS
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("UNEXPECTED_SUCCESS", result.stdout)

    def test_missing_checksum_is_rejected(self):
        result = self.run_shell("""
ARCHIVE_PATH="$TEMP_DIR/image.tar"
printf image > "$ARCHIVE_PATH"
verify_archive
echo UNEXPECTED_SUCCESS
""")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Checksum file not found", result.stderr)
        self.assertNotIn("UNEXPECTED_SUCCESS", result.stdout)

    def test_main_routes_domestic_archive_and_default_online_install(self):
        for mirror in ("cn", "default"):
            with self.subTest(mirror=mirror):
                result = self.run_shell(
                    """
ROOT_DIR="$TEST_DIR"
IMAGE_REPOSITORY=local/taccap; IMAGE_TAG=local-test
if [[ "$MIRROR" == cn ]]; then
  printf image > "$ROOT_DIR/xense-taccap-lerobot-local-test-linux-amd64.tar"
  (cd "$ROOT_DIR"; sha256sum *.tar > SHA256SUMS)
fi
require_normal_user() { :; }
load_os_release() { DISTRO_ID=ubuntu; DISTRO_CODENAME=jammy; }
install_docker() { echo HOST_INSTALL; }
configure_docker_proxy() { :; }
configure_docker_access() { :; }
install_nvidia_container_toolkit() { :; }
install_udev_rules() { :; }
sudo() { :; }
load_image_from_archive() { echo LOCAL_LOAD; }
pull_image() { echo ONLINE_PULL; }
verify_image() { echo IMAGE_CHECK; }
main
""",
                    mirror=mirror,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Installation completed successfully", result.stdout)
                self.assertIn("IMAGE_CHECK", result.stdout)
                if mirror == "cn":
                    self.assertIn("LOCAL_LOAD", result.stdout)
                    self.assertNotIn("ONLINE_PULL", result.stdout)
                    self.assertLess(result.stdout.index(": OK"), result.stdout.index("HOST_INSTALL"))
                else:
                    self.assertIn("ONLINE_PULL", result.stdout)
                    self.assertNotIn("LOCAL_LOAD", result.stdout)

    def test_smoke_test_uses_loaded_image_without_pull(self):
        result = self.run_shell("""
IMAGE_REPOSITORY=local/taccap; IMAGE_TAG=local-test
locate_compose_file() { COMPOSE_FILE=/unused/compose.yaml; }
mock_docker() {
  printf 'IMAGE=%s:%s ARGS=%s\\n' "$LEROBOT_IMAGE" "$LEROBOT_IMAGE_TAG" "$*"
  printf 'SMOKE cuda=ok\\nSMOKE graphics=ok\\n'
}
DOCKER_CMD=(mock_docker)
verify_image
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IMAGE=local/taccap:local-test", result.stdout)
        self.assertIn("--pull never", result.stdout)

    def test_smoke_test_preserves_image_when_docker_requires_sudo(self):
        result = self.run_shell("""
IMAGE_REPOSITORY=local/taccap; IMAGE_TAG=local-test
docker() { return 1; }
sudo() {
  case "$1" in
    groupadd|usermod) return 0 ;;
  esac
  # Assert assignments are sudo arguments, not inherited environment which
  # sudo's default env_reset would strip on a newly installed host.
  test "$1" = LEROBOT_IMAGE=local/taccap || return 99
  test "$2" = LEROBOT_IMAGE_TAG=local-test || return 99
  test "$3" = docker || return 99
  printf 'SUDO_ARGS=%s\\n' "$*"
  printf 'SMOKE cuda=ok\\nSMOKE graphics=ok\\n'
}
locate_compose_file() { COMPOSE_FILE=/unused/compose.yaml; }
configure_docker_access
verify_image
""")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SUDO_ARGS=LEROBOT_IMAGE=local/taccap LEROBOT_IMAGE_TAG=local-test docker compose", result.stdout)
        self.assertIn("--pull never", result.stdout)

    def test_image_repository_environment_precedence(self):
        for preferred in ("", "preferred/taccap"):
            with self.subTest(preferred=preferred):
                result = subprocess.run(
                    ["bash", "-c", INSTALLER + '\nprintf "%s\\n" "$IMAGE_REPOSITORY"'],
                    env=self.installer_env(LEROBOT_IMAGE=preferred, XENSE_IMAGE_REPOSITORY="legacy/taccap"),
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), preferred or "legacy/taccap")

    def test_delivery_preserves_image_reference_and_disables_pull(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            docker = base / "docker"
            docker.write_text("""#!/bin/bash
set -eu
case "$1" in
  image) [[ "$*" != *--format* ]] || echo amd64 ;;
  save) (umask 077; printf test-image > "$3") ;;
  *) exit 99 ;;
esac
""")
            docker.chmod(0o755)
            result = subprocess.run(
                ["bash", str(ROOT / "docker/package_customer_delivery.sh"), "local-test"],
                env=self.installer_env(
                    PATH=f"{base}:{os.environ['PATH']}",
                    LEROBOT_IMAGE="local/taccap",
                    XENSE_IMAGE_REPOSITORY="legacy/unused",
                    XENSE_DIST_DIR=str(base / "dist"),
                ),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            bundle = base / "dist/xense-taccap-lerobot-local-test-linux-amd64"
            self.assertEqual(
                (bundle / ".env").read_text(), "LEROBOT_IMAGE=local/taccap\nLEROBOT_IMAGE_TAG=local-test\n"
            )
            self.assertIn("pull_policy: never", (bundle / "compose.override.yaml").read_text())
            self.assertEqual((bundle / "delivery.env").read_text(), (bundle / ".env").read_text())
            self.assertEqual(next(bundle.glob("*.tar")).stat().st_mode & 0o777, 0o644)
            self.assertEqual((bundle / "install_cn.sh").stat().st_mode & 0o777, 0o755)
            self.assertIn("XENSE_MIRROR=cn", (bundle / "install_cn.sh").read_text())
            self.assertEqual((bundle / "README.md").read_text(), (ROOT / "docker/CUSTOMER_README_ZH.md").read_text())
            # The generated entry point must also work from another directory.
            help_result = subprocess.run(
                ["bash", str(bundle / "install_cn.sh"), "--help"], cwd=base, capture_output=True, text=True
            )
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn("XENSE_MIRROR=cn", help_result.stdout)
            checksum = subprocess.run(
                ["sha256sum", "--check", "SHA256SUMS"], cwd=bundle, capture_output=True, text=True
            )
            self.assertEqual(checksum.returncode, 0, checksum.stderr)


if __name__ == "__main__":
    unittest.main()
