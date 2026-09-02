#!/usr/bin/env bash
set -euo pipefail

cd /opt/seo-app

total_profiles="${1:-11256}"
batch_size="${2:-500}"
workers="${3:-12}"
run_name="${4:-creator-contact-full-20260902}"
parts_dir="outputs/${run_name}-parts"
status_file="/tmp/${run_name}.status"
app_container_id="$(docker compose ps -q app)"

mkdir -p "${parts_dir}"
rm -f "${status_file}"

finish() {
    result=$?
    echo "${result}" > "${status_file}"
    exit "${result}"
}
trap finish EXIT

docker cp scripts/enrich_creator_catalog_contacts.py "${app_container_id}:/tmp/enrich_creator_catalog_contacts.py"
docker cp scripts/validate_creator_contact_research.py "${app_container_id}:/tmp/validate_creator_contact_research.py"

for ((offset = 0; offset < total_profiles; offset += batch_size)); do
    validated_name="creator-contact-part-${offset}-validated.json"
    if [[ -s "${parts_dir}/${validated_name}" ]]; then
        echo "SKIP_COMPLETED_OFFSET:${offset}"
        continue
    fi
    echo "RESEARCH_OFFSET:${offset}"
    docker compose exec -T app env PYTHONPATH=/app/src python /tmp/enrich_creator_catalog_contacts.py \
        --offset "${offset}" \
        --limit "${batch_size}" \
        --workers "${workers}" \
        --output "/tmp/creator-contact-part-${offset}.json"
    docker compose exec -T app python /tmp/validate_creator_contact_research.py \
        "/tmp/creator-contact-part-${offset}.json" \
        --output "/tmp/${validated_name}" \
        --workers "${workers}"
    docker cp "${app_container_id}:/tmp/creator-contact-part-${offset}.json" "${parts_dir}/"
    docker cp "${app_container_id}:/tmp/${validated_name}" "${parts_dir}/"
    echo "COMPLETED_OFFSET:${offset}"
done

echo "RESEARCH_COMPLETE"
for ((offset = 0; offset < total_profiles; offset += batch_size)); do
    validated_name="creator-contact-part-${offset}-validated.json"
    echo "DRY_RUN_OFFSET:${offset}"
    docker cp "${parts_dir}/${validated_name}" "${app_container_id}:/tmp/${validated_name}"
    docker compose exec -T app env PYTHONPATH=/app/src python /tmp/enrich_creator_catalog_contacts.py \
        --input-report "/tmp/${validated_name}"
done

echo "DRY_RUN_COMPLETE"
for ((offset = 0; offset < total_profiles; offset += batch_size)); do
    validated_name="creator-contact-part-${offset}-validated.json"
    echo "APPLY_OFFSET:${offset}"
    docker compose exec -T app env PYTHONPATH=/app/src python /tmp/enrich_creator_catalog_contacts.py \
        --input-report "/tmp/${validated_name}" \
        --apply
done

trap - EXIT
echo 0 > "${status_file}"
echo "COMPLETE"
