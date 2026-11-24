#!/usr/bin/env bash
# OmniRoute gateway (MIT): one local endpoint over 400+ models with automatic fallback, so a
# rate-limited free provider never stops the work. tools/ai.py and tools/worker.py use it as a safety net.
#   bash tools/omni.sh start | stop | status | models
K=$(cat ~/.paper-cinema/omniroute-key 2>/dev/null)
case "$1" in
  start) pgrep -f "omniroute --headless" >/dev/null && { echo "already running"; exit 0; }
         (nohup omniroute --headless --port 20128 > /tmp/omniroute.log 2>&1 &); sleep 45
         curl -s -o /dev/null -w "gateway: %{http_code}\n" http://localhost:20128/v1/models -H "Authorization: Bearer $K" ;;
  stop)  pkill -f "omniroute --headless" && echo stopped ;;
  status) curl -s -o /dev/null -w "gateway: %{http_code} (200 = up)\n" http://localhost:20128/v1/models -H "Authorization: Bearer $K" ;;
  models) curl -s http://localhost:20128/v1/models -H "Authorization: Bearer $K" | python3 -c "import json,sys;d=json.load(sys.stdin)['data'];print(len(d),'models');[print(' ',m['id']) for m in d[:25]]" ;;
  *) echo "usage: bash tools/omni.sh start|stop|status|models" ;;
esac
