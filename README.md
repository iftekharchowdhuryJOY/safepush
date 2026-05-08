# safepush

Safe git automation CLI with denylist + content scanning + audit logging.

## Install (dev)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .

# Commands

safepush scan
safepush doctor
safepush config init

Safety model
denylist path blocking
regex-based secret scanning
basic PII scanning
fail-closed scanner behavior
local audit log