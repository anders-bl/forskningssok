#!/bin/sh
# Bygger ../tiptap.js fra entry.js. Kjør kun ved oppgradering; resultatet committes.
set -e
cd "$(dirname "$0")"
npm install --no-audit --no-fund --silent
npx esbuild entry.js --bundle --minify --format=iife --target=es2020 --outfile=../tiptap.js
echo "MIT-lisenser: se node_modules/@tiptap/core/LICENSE.md, node_modules/tiptap-markdown/LICENSE" 
ls -la ../tiptap.js
