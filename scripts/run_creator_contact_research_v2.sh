#!/usr/bin/env bash
set -euo pipefail

cd /opt/seo-app

batch_size="${1:-250}"
workers="${2:-16}"
run_name="${3:-creator-contact-v2-20260902}"
parts_dir="outputs/${run_name}-parts"
status_file="/tmp/${run_name}.status"
app_container_id="$(docker compose ps -q app)"
batch_number=0

mkdir -p "${parts_dir}"
rm -f "${status_file}"

finish() {
    result=$?
    echo "${result}" > "${status_file}"
    exit "${result}"
}
trap finish EXIT

docker cp scripts/enrich_creator_catalog_contacts.py "${app_container_id}:/tmp/enrich_creator_catalog_contacts_v2.py"
docker cp scripts/validate_creator_contact_research.py "${app_container_id}:/tmp/validate_creator_contact_research.py"

while true; do
    raw_name="creator-contact-v2-part-${batch_number}.json"
    validated_name="creator-contact-v2-part-${batch_number}-validated.json"
    echo "RESEARCH_BATCH:${batch_number}"
    summary="$(docker compose exec -T app env PYTHONPATH=/app/src python /tmp/enrich_creator_catalog_contacts_v2.py \
        --only-without-contact \
        --only-unresearched-version \
        --limit "${batch_size}" \
        --workers "${workers}" \
        --output "/tmp/${raw_name}")"
    echo "${summary}"
    profile_count="$(printf '%s' "${summary}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["profile_count"])')"
    if [[ "${profile_count}" == "0" ]]; then
        break
    fi
    docker compose exec -T app python /tmp/validate_creator_contact_research.py \
        "/tmp/${raw_name}" \
        --output "/tmp/${validated_name}" \
        --workers "${workers}"
    docker cp "${app_container_id}:/tmp/${raw_name}" "${parts_dir}/${raw_name}"
    docker cp "${app_container_id}:/tmp/${validated_name}" "${parts_dir}/${validated_name}"
    docker compose exec -T app env PYTHONPATH=/app/src python /tmp/enrich_creator_catalog_contacts_v2.py \
        --input-report "/tmp/${validated_name}" \
        --apply
    echo "COMPLETED_BATCH:${batch_number}"
    batch_number=$((batch_number + 1))
done

trap - EXIT
echo 0 > "${status_file}"
echo "COMPLETE:${batch_number}"
