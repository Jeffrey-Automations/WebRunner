# WebRunner runner image: Python, the je_web_runner package, Chromium and chromedriver.
# It runs action files headless, so a CI job or a Kubernetes shard Job needs no setup of its own.
#
# Build (BuildKit or buildah >= 1.27; the context is docker/, which keeps it small):
#   docker build -f docker/Runner.Containerfile -t webrunner-runner docker
# Build with another package: a pinned release or the dev channel
#   docker build -f docker/Runner.Containerfile --build-arg WEBRUNNER_PACKAGE=je_web_runner==0.0.94 docker
#   docker build -f docker/Runner.Containerfile --build-arg WEBRUNNER_PACKAGE=je_web_runner_dev docker
# or a local wheel: name the directory that holds it as the build context "wheels", which replaces
# the empty stage of that name and is mounted read-only at /wheels while pip runs (no layer added):
#   docker build -f docker/Runner.Containerfile --build-context wheels=dist \
#     --build-arg WEBRUNNER_PACKAGE=/wheels/<wheel file> docker
#
# Run (action files mounted at the working directory /work; reports and WEBRunner.log are written
# there, so the directory must be writable by the container user):
#   docker run --rm --shm-size=1g -v "$PWD:/work" webrunner-runner -d actions --report reports/run
#   docker run --rm --shm-size=1g -v "$PWD:/work" webrunner-runner -d actions --shard 1/4 --fail-fast
# On Linux pass --user "$(id -u):$(id -g)" when the mounted directory is not world-writable.
#
# What an action file must do in this image:
#   ["WR_set_driver", {"webdriver_name": "chrome", "install_driver": false,
#                      "options": ["--headless=new", "--no-sandbox", "--disable-dev-shm-usage"]}]
#   - install_driver false: the image already has chromedriver; the default downloads another one.
#   - --no-sandbox: Chromium's sandbox needs privileges an unprivileged container does not have.
#
# Not verified, because this file was written without building it:
#   - that the image builds at all, and its size;
#   - that the Debian chromium / chromium-driver pair starts under the uid below with the options above;
#   - that SE_CHROMEDRIVER makes Selenium use /usr/bin/chromedriver for every Selenium release pip may
#     resolve (read from Selenium 4.41 sources: a driver path from the environment skips Selenium Manager);
#   - the RUN --mount line and --build-context under builders other than BuildKit.

# ---- Stage "wheels": empty. `--build-context wheels=<dir>` replaces it with a directory of local wheels.
FROM scratch AS wheels

# ---- Stage "runner", the image. Base: the newest interpreter line CI publishes with. Pinned by
# version tag, not by digest: docker/IssueWorker.Containerfile pins by tag as well, so the repository
# holds no digest to reuse.
FROM python:3.12-slim-bookworm AS runner

# ---- Browser: Chromium and the chromedriver built for it, from the distribution, so the two always
# match. One layer, package lists removed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# ---- Package: installed from the build argument. Wheels only, so no build backend runs as root.
ARG WEBRUNNER_PACKAGE=je_web_runner
RUN --mount=type=bind,from=wheels,target=/wheels,readonly \
    python -m pip install --no-cache-dir --only-binary :all: "${WEBRUNNER_PACKAGE}"

# ---- User and directories: a fixed non-root uid (numeric, so Kubernetes runAsNonRoot can check it)
# with a home for the browser profile and caches, and /work for the mounted action files. Both are
# world-writable with the sticky bit so `docker run --user <host uid>` works too.
RUN useradd --uid 65532 --user-group --create-home --home-dir /home/webrunner webrunner \
    && mkdir -p /work \
    && chown 65532:65532 /work \
    && chmod 1777 /work /home/webrunner

# ---- Runtime settings: no secrets here; pass them at run time (-e / --env-file / a mounted .env).
ENV HOME=/home/webrunner \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SE_CHROMEDRIVER=/usr/bin/chromedriver

USER 65532:65532
WORKDIR /work

# The CLI is the entrypoint: arguments to `docker run <image>` are WebRunner arguments.
ENTRYPOINT ["webrunner"]
CMD ["--help"]
