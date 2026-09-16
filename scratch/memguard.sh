#!/bin/bash
# 用法: memguard.sh <limit_MB> <log> cmd...  —— 进程树总 RSS 超限就杀掉，并记录峰值
LIMIT=$1; LOG=$2; shift 2
"$@" > "$LOG" 2>&1 & PID=$!
PEAK=0
while kill -0 $PID 2>/dev/null; do
  KIDS=$(pgrep -P $PID; for k in $(pgrep -P $PID); do pgrep -P $k; done)
  RSS=$(ps -o rss= -p $PID $KIDS 2>/dev/null | awk '{s+=$1} END {print int(s/1024)}')
  [ "$RSS" -gt "$PEAK" ] && PEAK=$RSS
  if [ "$RSS" -gt "$LIMIT" ]; then pkill -P $PID; kill $PID; echo "KILLED at ${RSS}MB" >> "$LOG"; break; fi
  sleep 0.5
done
wait $PID; echo "exit=$? peak_tree_rss_MB=$PEAK" >> "$LOG"
