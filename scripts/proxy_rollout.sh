#!/usr/bin/env bash
set -euo pipefail

cd /opt/seo-app

STAGE="${1:-1}" # 1 | 2 | pool
TEST_ORG_URL="${TEST_ORG_URL:-https://yandex.ru/maps/org/186769473007/}"
COUNTRIES_CSV="${PROXY_TEST_COUNTRIES:-base,kz,am,ge}"
TMP_FILE="$(mktemp /tmp/proxy_probe.XXXXXX)"
trap 'rm -f "$TMP_FILE"' EXIT

echo "[proxy-rollout] stage=${STAGE}"
echo "[proxy-rollout] test_org_url=${TEST_ORG_URL}"

_curl_probe() {
  # args: username password url maxtime
  local _username="$1"
  local _password="$2"
  local _url="$3"
  local _maxtime="$4"
  local out
  out="$(curl -sS -o /dev/null -w "%{http_code}|%{time_total}" \
    --max-time "${_maxtime}" \
    --proxy "brd.superproxy.io:33335" \
    --proxy-user "${_username}:${_password}" \
    -k -L "${_url}" 2>/dev/null || true)"
  local code
  local t
  code="$(echo "${out}" | cut -d'|' -f1)"
  t="$(echo "${out}" | cut -d'|' -f2)"
  if [[ -z "${code}" || "${code}" == "000" ]]; then
    echo "0|999"
    return
  fi
  if [[ "${code}" -ge 200 && "${code}" -lt 400 ]]; then
    echo "1|${t}"
    return
  fi
  echo "0|${t}"
}

while IFS='|' read -r proxy_id proxy_type host port username password; do
  [[ -z "${proxy_id}" ]] && continue
  best_score="-1"
  best_avg="999"
  best_country="base"

  IFS=',' read -r -a countries <<< "${COUNTRIES_CSV}"
  for country in "${countries[@]}"; do
    country="$(echo "${country}" | tr '[:upper:]' '[:lower:]' | xargs)"
    [[ -z "${country}" ]] && continue

    local_user="${username}-session-$((RANDOM%900000+100000))"
    if [[ "${country}" != "base" ]]; then
      local_user="${local_user}-country-${country}"
    fi

    geo_probe="$(_curl_probe "${local_user}" "${password}" "https://geo.brdtest.com/welcome.txt?product=resi&method=native" 14)"
    ymap_probe="$(_curl_probe "${local_user}" "${password}" "https://yandex.ru/maps/" 18)"
    org_probe="$(_curl_probe "${local_user}" "${password}" "${TEST_ORG_URL}" 28)"

    geo_ok="$(echo "${geo_probe}" | cut -d'|' -f1)"
    ymap_ok="$(echo "${ymap_probe}" | cut -d'|' -f1)"
    org_ok="$(echo "${org_probe}" | cut -d'|' -f1)"
    geo_t="$(echo "${geo_probe}" | cut -d'|' -f2)"
    ymap_t="$(echo "${ymap_probe}" | cut -d'|' -f2)"
    org_t="$(echo "${org_probe}" | cut -d'|' -f2)"

    score=$((geo_ok + ymap_ok + org_ok))
    avg_time="$(awk -v a="${geo_t}" -v b="${ymap_t}" -v c="${org_t}" 'BEGIN{printf "%.3f", (a+b+c)/3.0}')"

    if [[ "${score}" -gt "${best_score}" ]]; then
      best_score="${score}"
      best_avg="${avg_time}"
      best_country="${country}"
    elif [[ "${score}" -eq "${best_score}" ]]; then
      better="$(awk -v a="${avg_time}" -v b="${best_avg}" 'BEGIN{if (a < b) print 1; else print 0}')"
      if [[ "${better}" == "1" ]]; then
        best_avg="${avg_time}"
        best_country="${country}"
      fi
    fi

    echo "[probe] id=${proxy_id} country=${country} score=${score}/3 avg=${avg_time}s"
  done

  echo "${proxy_id}|${best_score}|${best_avg}|${best_country}|${username}" >> "${TMP_FILE}"
done < <(docker compose exec -T postgres psql -U beautybot -d local -At -F '|' -P null='' -c "SELECT id,proxy_type,host,port,username,password FROM proxyservers ORDER BY created_at")

echo "[probe-summary]"
cat "${TMP_FILE}" | sort -t'|' -k2,2nr -k3,3n

target_count=1
if [[ "${STAGE}" == "2" ]]; then
  target_count=2
elif [[ "${STAGE}" == "pool" ]]; then
  target_count=99
fi

mapfile -t selected_ids < <(cat "${TMP_FILE}" | sort -t'|' -k2,2nr -k3,3n | awk -F'|' '$2 >= 2 {print $1}' | head -n "${target_count}")

echo "[rollout] selected_count=${#selected_ids[@]} ids=${selected_ids[*]:-none}"

docker compose exec -T postgres psql -U beautybot -d local -c "
  UPDATE proxyservers
  SET is_active = FALSE,
      updated_at = CURRENT_TIMESTAMP;
" >/dev/null

if [[ "${#selected_ids[@]}" -gt 0 ]]; then
  for pid in "${selected_ids[@]}"; do
    docker compose exec -T postgres psql -U beautybot -d local -c "
      UPDATE proxyservers
      SET is_active = TRUE,
          is_working = TRUE,
          last_checked_at = CURRENT_TIMESTAMP,
          updated_at = CURRENT_TIMESTAMP
      WHERE id = '${pid}';
    " >/dev/null
  done
fi

if [[ "${#selected_ids[@]}" -gt 0 ]]; then
  if grep -q '^PARSING_USE_PROXY_POOL=' .env; then
    sed -i 's/^PARSING_USE_PROXY_POOL=.*/PARSING_USE_PROXY_POOL=true/' .env
  else
    echo 'PARSING_USE_PROXY_POOL=true' >> .env
  fi
else
  if grep -q '^PARSING_USE_PROXY_POOL=' .env; then
    sed -i 's/^PARSING_USE_PROXY_POOL=.*/PARSING_USE_PROXY_POOL=false/' .env
  else
    echo 'PARSING_USE_PROXY_POOL=false' >> .env
  fi
fi

best_country_global="$(cat "${TMP_FILE}" | sort -t'|' -k2,2nr -k3,3n | head -n1 | cut -d'|' -f4)"
if [[ -n "${best_country_global}" && "${best_country_global}" != "base" ]]; then
  if grep -q '^PROXY_FORCE_COUNTRY=' .env; then
    sed -i "s/^PROXY_FORCE_COUNTRY=.*/PROXY_FORCE_COUNTRY=${best_country_global}/" .env
  else
    echo "PROXY_FORCE_COUNTRY=${best_country_global}" >> .env
  fi
  echo "[rollout] PROXY_FORCE_COUNTRY=${best_country_global}"
fi

echo "[db-state]"
docker compose exec -T postgres psql -U beautybot -d local -c "
  SELECT id, host, is_active, is_working, success_count, failure_count, last_checked_at
  FROM proxyservers
  ORDER BY created_at;
"

echo "[done] restart workers to apply env changes: docker compose restart worker"
