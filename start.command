#!/bin/sh
# macOS: double-click after installing dependencies as described in README.
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then
    tg_python=.venv/bin/python
elif [ -x ../../work/venv/bin/python ]; then
    tg_python=../../work/venv/bin/python
else
    printf '%s\n' '请先按 README 安装依赖：python3 -m venv .venv，然后安装 requirements.txt。'
    exit 1
fi
exec "$tg_python" -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
