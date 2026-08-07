#!/usr/bin/env bash

set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: bash _checkout/build.sh OUTPUT_DIRECTORY" >&2
  exit 64
fi

checkout_source_dir="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(cd "${checkout_source_dir}/.." && pwd)"
output_dir="$1"

if [ -e "${output_dir}" ] && [ -n "$(find "${output_dir}" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
  echo "Output directory must be empty: ${output_dir}" >&2
  exit 65
fi

mkdir -p "${output_dir}/Assets" "${output_dir}/become-a-member"

cp "${checkout_source_dir}/_headers" "${output_dir}/_headers"
cp "${checkout_source_dir}/_redirects" "${output_dir}/_redirects"
cp "${checkout_source_dir}/robots.txt" "${output_dir}/robots.txt"
cp "${checkout_source_dir}/404.html" "${output_dir}/404.html"
cp "${checkout_source_dir}/favicon.svg" "${output_dir}/favicon.svg"
cp "${checkout_source_dir}/script.js" "${output_dir}/script.js"
cp "${checkout_source_dir}/become-a-member/index.html" "${output_dir}/become-a-member/index.html"
cp "${repo_root}/style.css" "${output_dir}/style.css"
cp "${repo_root}/donation.js" "${output_dir}/donation.js"
cp "${repo_root}/Assets/events.png" "${output_dir}/Assets/events.png"
