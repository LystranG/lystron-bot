MAINTAINER LystranG

ARG PYTHON_VERSION=3.11
FROM ghcr.1ms.run/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim

RUN useradd -m -u 1000 nonebot

WORKDIR /app

ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked \

# 让运行期默认使用 uv 创建的虚拟环境
ENV PATH="/app/.venv/bin:${PATH}"

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT []

# Use the non-root user to run our application
RUN chown -R nonebot:nonebot /app
USER nonroot

EXPOSE 8080

CMD ["uv", "run", "bot.py"]
