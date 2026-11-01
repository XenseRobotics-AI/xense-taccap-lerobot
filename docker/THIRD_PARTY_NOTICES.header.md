# Third-Party Notices — xense-taccap-lerobot image

Image version: {{IMAGE_VERSION}} · Generated at build time: {{DATE}}

This container image is distributed by 千觉机器人科技（上海）有限公司 (Xense Robotics).
Besides Xense software, it contains third-party open-source and redistributable
components. Each component is licensed under its own terms, listed below, and
nothing in the Xense license changes those terms. This file is generated
automatically from the packages actually installed in this image.

## Base image and container tooling

- Base operating system: Ubuntu 22.04 (`public.ecr.aws/ubuntu/ubuntu`). Ubuntu
  packages are licensed individually; see the Debian packages table.
- The image does **not** contain Docker Engine, Docker Desktop, containerd or
  any other Docker, Inc. software. It runs on any OCI-compatible runtime. The
  host install script (`docker/install_customer.sh`) installs Docker Engine
  Community Edition (Apache-2.0) from the official Docker apt repository.

## Upstream projects

- LeRobot — © Hugging Face Inc., Apache License 2.0
  (https://github.com/huggingface/lerobot). This image's LeRobot is a modified
  fork; modifications © Xense Robotics, Apache License 2.0. See
  `/opt/lerobot/LICENSE`.

## Source code offer

For every component under the GNU GPL, LGPL or any other license that requires
source distribution, the corresponding source code is available:

1. from the upstream locations listed in the tables below (PyPI, conda-forge,
   the Ubuntu archive via `apt-get source <package>`), for the exact versions
   listed; and
2. on request from Xense Robotics for at least three years after we last
   distribute this image version. Contact: the support channel listed in your
   delivery documentation.

## Replacing LGPL components

LGPL-licensed Python packages and shared libraries in this image are loaded
dynamically. You may replace them with modified versions, for example
`pip install --force-reinstall <your-build>` inside the container.
