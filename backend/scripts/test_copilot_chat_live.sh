#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8010}"
ENDPOINT="${BASE_URL}/api/copilot/chat"

post() {
  local name="$1"
  local payload="$2"
  echo "=== ${name} ==="
  curl -sS -w "\nHTTP %{http_code}\n" -X POST "${ENDPOINT}" \
    -H "Content-Type: application/json" \
    -d "${payload}"
  echo
}

post "P0-闲聊" '{"user_input":"你好"}'
post "P0-查物流" '{"user_input":"帮我查一下订单12345678的物流状态"}'
post "P0-小额退款" '{"user_input":"客户要求对订单12345678退款50元，我同意退款"}'
post "P0-大额拦截" '{"user_input":"客户要求对订单12345678退款200元，我同意退款"}'
post "P1-边界100" '{"user_input":"客户要求对订单12345678退款100元，我同意退款"}'
post "P1-边界101" '{"user_input":"客户要求对订单12345678退款101元，我同意退款"}'
post "P2-参数校验" '{"message":"你好"}'
