#!/bin/sh
# Bump the cache-busting version on every planner module import (phones and the Quest keep old modules otherwise).
# usage: sh tools/planner/bump.sh p3
cd "$(dirname "$0")/../.." || exit 1
v="$1"; [ -n "$v" ] || { echo "usage: bump.sh <version>"; exit 1; }
for f in src/planner/*.js; do
  sed -i '' -E "s#(from \"\./[a-z0-9]+\.js)(\?v=[a-z0-9]+)?\"#\1?v=$v\"#g; s#(import\(\"\./[a-z0-9]+\.js)(\?v=[a-z0-9]+)?\"\)#\1?v=$v\")#g" "$f"
done
sed -i '' -E "s#src/planner/app\.js(\?v=[a-z0-9]+)?#src/planner/app.js?v=$v#" planner.html
grep -ho '\?v=[a-z0-9]*' src/planner/*.js planner.html | sort | uniq -c
