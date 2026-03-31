#!/bin/sh
# Runs as root: fix volume permissions, then drop to rlmob

chown -R rlmob:rlmob /app/inputs /app/output /app/rlmobtest/config 2>/dev/null || true
find /app/inputs -name "gradlew" -exec chmod +x {} \; 2>/dev/null || true

exec gosu rlmob "$@"
