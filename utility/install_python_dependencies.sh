#!/bin/bash

WORK_DIR="$(dirname "$0")"
PROJECT_DIR="$(dirname "$WORK_DIR")"

uv --version >/dev/null 2>&1 || {
    echo >&2 -e "\nuv is required but it's not installed."
    echo >&2 -e "You can install it by running the following command:\n"
    echo >&2 "curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo >&2 -e "\n"
    echo >&2 -e "\nFor more information, see uv documentation: https://docs.astral.sh/uv/"
    exit 1;
}

cd "$PROJECT_DIR" && uv sync --group dev
