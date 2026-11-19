#!/bin/bash
# Shared helpers for backup.sh, restore.sh and verify_restore.sh.
# Sourced, not executed. Callers set DB_HOST, DB_USER, DB_NAME (live database).
#
# Why a restore needs more than `pg_restore`: Apache AGE keeps its catalog in
# two extension config tables, ag_catalog.ag_graph and ag_catalog.ag_label,
# and ag_label has a foreign key (fk_graph_oid) onto ag_graph. pg_dump writes
# their rows as ordinary TABLE DATA entries, but pg_restore does not order data
# by foreign keys. A parallel restore (-j) loads ag_label alongside ag_graph,
# the COPY into ag_label fails the foreign key, and the graph comes back with
# its vertex/edge tables but no labels; the first cypher query against that
# database crashed the server (signal 11). `pg_restore --clean` into an
# existing database is no better: AGE refuses to drop label tables ("table X
# is for label X") and the graph rows are appended a second time.
#
# restore_dump below therefore always restores into an EMPTY database in four
# explicit steps: schema, then the AGE catalog rows (ag_graph before ag_label,
# serially), then all other data, then indexes/constraints. check_graph then
# proves the graph is usable before anything runs cypher against it.

# ── Small utilities ───────────────────────────────────────────

json_str() {
    # Escape a value for use inside a JSON string literal.
    local s=${1//\\/\\\\}
    s=${s//\"/\\\"}
    s=${s//$'\n'/ }
    s=${s//$'\r'/ }
    s=${s//$'\t'/ }
    printf '%s' "$s"
}

psql_db() {
    # psql_db <db> <sql> — one query, unaligned tuples only, fail on error.
    psql -h "$DB_HOST" -U "$DB_USER" -d "$1" -X -qAt -v ON_ERROR_STOP=1 -c "$2"
}

# ── job_runs + owner notifications ────────────────────────────

record_job_run() {
    # record_job_run <job_name> <status> <result_json> [error_text]
    # Values go through psql variables, so quotes in an error message can no
    # longer break (or inject into) the INSERT.
    local job=$1 status=$2 result=$3 error=${4:-}
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -X -q -v ON_ERROR_STOP=1 \
        -v job="$job" -v status="$status" -v started="${STARTED_AT:-now}" \
        -v result="$result" -v err="$error" <<'SQL' \
        || echo "[$(date)] WARNING: could not record job run ($job/$status)"
INSERT INTO job_runs (id, tenant_id, job_name, status, started_at, completed_at,
                      result, error, attempt, created_at)
VALUES (gen_random_uuid(), 'system', :'job', :'status', :'started'::timestamptz, now(),
        :'result'::jsonb, NULLIF(:'err', ''), 1, now());
SQL
}

notify_owner() {
    # notify_owner <code> <priority: important|info> <title> <body>
    # One row in `notifications` (what the phone polls), at most once per code
    # per UTC day. Recipients: BACKUP_ALERT_TENANTS (comma-separated), else the
    # tenant that owns the most memories — on a personal install, the owner.
    local code=$1 prio=$2 title=$3 body=$4
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -X -q -v ON_ERROR_STOP=1 \
        -v code="$code" -v prio="$prio" -v title="$title" -v body="$body" \
        -v tenants="${BACKUP_ALERT_TENANTS:-}" <<'SQL' \
        || echo "[$(date)] WARNING: could not write owner notification ($code)"
WITH configured AS (
    SELECT trim(t) AS tenant_id FROM unnest(string_to_array(:'tenants', ',')) AS t
    WHERE trim(t) <> ''
), recipients AS (
    SELECT tenant_id FROM configured
    UNION ALL
    SELECT tenant_id FROM (
        SELECT tenant_id FROM memories GROUP BY tenant_id ORDER BY count(*) DESC LIMIT 1
    ) owner WHERE NOT EXISTS (SELECT 1 FROM configured)
), k AS (
    SELECT 'backup:' || :'code' || ':' || to_char(now() AT TIME ZONE 'UTC', 'YYYYMMDD') AS key
)
INSERT INTO notifications (tenant_id, priority, title, body, metadata,
                           is_delivered, delivered_at, source_type)
SELECT r.tenant_id, :'prio', left(:'title', 500), :'body',
       jsonb_build_object('kind', 'backup', 'code', :'code', 'dedup_key', k.key),
       true, now(), 'backup'
FROM recipients r CROSS JOIN k
WHERE NOT EXISTS (
    SELECT 1 FROM notifications n
    WHERE n.tenant_id = r.tenant_id AND n.source_type = 'backup'
      AND n.metadata->>'dedup_key' = k.key
);
SQL
}

# ── AGE graph inventory ───────────────────────────────────────

# One line per (graph, label): graph|label|kind|rows. Rows are counted on the
# label's table including inheritance children — the same set a cypher MATCH
# on that label returns (the base labels _ag_label_vertex/_ag_label_edge hold
# every vertex/edge). A graph without labels shows as graph|-|-|0.
GRAPH_COUNTS_SQL="SELECT g.name || '|' || coalesce(l.name::text, '-') || '|' || coalesce(l.kind::text, '-') || '|' ||
       CASE WHEN l.relation IS NULL THEN '0'
            ELSE (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %s', l.relation),
                  false, true, '')))[1]::text END
FROM ag_catalog.ag_graph g LEFT JOIN ag_catalog.ag_label l ON l.graph = g.graphid
ORDER BY g.name::text COLLATE \"C\", l.name::text COLLATE \"C\""

has_age() {
    # has_age <db> — prints t/f
    psql_db "$1" "SELECT to_regclass('ag_catalog.ag_label') IS NOT NULL"
}

graph_counts() {
    # graph_counts <db> — inventory lines (empty when AGE is not installed)
    local age
    age=$(has_age "$1") || return 1
    [ "$age" = "t" ] || return 0
    psql_db "$1" "$GRAPH_COUNTS_SQL"
}

# ── Dump ──────────────────────────────────────────────────────

dump_with_manifest() {
    # dump_with_manifest <dump_path> <manifest_path>
    # pg_dump plus the graph inventory taken from the SAME snapshot (exported
    # by a read-only REPEATABLE READ transaction), so the restore drill can
    # demand exact label/vertex/edge counts instead of comparing a days-old
    # dump with the live graph. Read-only on the source database.
    local dump=$1 manifest=$2 snapshot="" line age
    age=$(has_age "$DB_NAME")
    coproc SNAPSESSION { psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -X -qAt -v ON_ERROR_STOP=1 2>&1; }
    local in=${SNAPSESSION[1]} out=${SNAPSESSION[0]}
    printf '%s\n' "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;" \
        "SELECT pg_export_snapshot();" >&"$in"
    IFS= read -r -t 60 snapshot <&"$out" || true
    if ! [[ $snapshot =~ ^[0-9A-F]+-[0-9A-F]+-[0-9]+$ ]]; then
        echo "[$(date)] ERROR: could not export a snapshot: $snapshot" >&2
        return 1
    fi
    pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" --snapshot="$snapshot" \
        --format=custom --compress=9 --file="$dump" || return 1
    : > "$manifest"
    if [ "$age" = "t" ]; then
        printf '%s;\n' "$GRAPH_COUNTS_SQL" >&"$in"
    fi
    printf '%s\n' "SELECT '__END__';" >&"$in"
    while IFS= read -r -t 120 line <&"$out"; do
        [ "$line" = "__END__" ] && break
        printf '%s\n' "$line" >> "$manifest"
    done
    [ "$line" = "__END__" ] || { echo "[$(date)] ERROR: graph inventory failed: $line" >&2; return 1; }
    printf '%s\n' "COMMIT;" '\q' >&"$in"
    wait "$SNAPSESSION_PID" 2>/dev/null || true
    return 0
}

# ── Restore ───────────────────────────────────────────────────

restore_dump() {
    # restore_dump <empty_db> <dump> <log_file>
    # Returns non-zero on the first pg_restore error (--exit-on-error); the
    # full pg_restore output is in <log_file>. RESTORE_JOBS (default 1) sets
    # parallelism for the data and post-data steps — safe here because the AGE
    # catalog rows are already loaded by then.
    local db=$1 dump=$2 log=$3 jobs=${RESTORE_JOBS:-1} tmp rc=0
    tmp=$(mktemp -d)
    local common=(-h "$DB_HOST" -U "$DB_USER" -d "$db" --no-owner --no-privileges --exit-on-error)
    : > "$log"
    pg_restore -l "$dump" > "$tmp/all.list" 2>> "$log" || { rm -rf "$tmp"; return 1; }
    # ag_graph first, then ag_label (the foreign key needs that order).
    grep -E '^[0-9]+; [0-9]+ [0-9]+ TABLE DATA ag_catalog ag_graph( |$)' "$tmp/all.list" > "$tmp/age.list" || true
    grep -E '^[0-9]+; [0-9]+ [0-9]+ TABLE DATA ag_catalog ag_label( |$)' "$tmp/all.list" >> "$tmp/age.list" || true
    grep -vE '^[0-9]+; [0-9]+ [0-9]+ TABLE DATA ag_catalog (ag_graph|ag_label)( |$)' "$tmp/all.list" > "$tmp/rest.list"

    echo "[$(date)] restore 1/4: schema" >> "$log"
    pg_restore "${common[@]}" --section=pre-data "$dump" >> "$log" 2>&1 || rc=$?
    if [ $rc -eq 0 ] && [ -s "$tmp/age.list" ]; then
        echo "[$(date)] restore 2/4: AGE catalog (ag_graph, ag_label)" >> "$log"
        pg_restore "${common[@]}" --data-only -L "$tmp/age.list" "$dump" >> "$log" 2>&1 || rc=$?
    fi
    if [ $rc -eq 0 ]; then
        echo "[$(date)] restore 3/4: data" >> "$log"
        pg_restore "${common[@]}" --section=data -L "$tmp/rest.list" -j "$jobs" "$dump" >> "$log" 2>&1 || rc=$?
    fi
    if [ $rc -eq 0 ]; then
        echo "[$(date)] restore 4/4: indexes and constraints" >> "$log"
        pg_restore "${common[@]}" --section=post-data -j "$jobs" "$dump" >> "$log" 2>&1 || rc=$?
    fi
    rm -rf "$tmp"
    # --exit-on-error stops at the first error; also refuse a "successful" run
    # that still printed errors.
    if [ $rc -eq 0 ] && grep -q 'error:' "$log"; then rc=1; fi
    return $rc
}

# ── Graph verification ────────────────────────────────────────

GRAPH_ERROR=""
GRAPH_JSON="{}"

check_graph() {
    # check_graph <restored_db> <expected_file> [baseline_name]
    # <expected_file> holds inventory lines (graph|label|kind|rows) from the
    # dump's manifest or the live database; an empty file means "no graph
    # expected". Sets GRAPH_ERROR on failure and GRAPH_JSON with the numbers.
    # Order matters: catalog and table checks are plain SQL; cypher runs only
    # once they pass, because cypher against a broken AGE catalog crashed the
    # server process (the drill runs on the live server).
    local db=$1 expected=$2 baseline=${3:-manifest} tmp got
    GRAPH_ERROR=""
    GRAPH_JSON="{}"
    tmp=$(mktemp -d)
    local exp_labels exp_v exp_e
    exp_labels=$(grep -vc '|-|-|' "$expected" || true)
    exp_v=$(awk -F'|' '$2=="_ag_label_vertex"{s+=$4} END{print s+0}' "$expected")
    exp_e=$(awk -F'|' '$2=="_ag_label_edge"{s+=$4} END{print s+0}' "$expected")

    if ! graph_counts "$db" > "$tmp/got" 2> "$tmp/err"; then
        GRAPH_ERROR="graph inventory query failed on restored copy: $(head -c 300 "$tmp/err")"
        rm -rf "$tmp"; return 1
    fi
    local got_labels got_v got_e
    got_labels=$(grep -vc '|-|-|' "$tmp/got" || true)
    got_v=$(awk -F'|' '$2=="_ag_label_vertex"{s+=$4} END{print s+0}' "$tmp/got")
    got_e=$(awk -F'|' '$2=="_ag_label_edge"{s+=$4} END{print s+0}' "$tmp/got")
    GRAPH_JSON="{\"baseline\": \"$baseline\", \"ag_label\": {\"expected\": $exp_labels, \"restored\": $got_labels}, \"vertices\": {\"expected\": $exp_v, \"restored\": $got_v}, \"edges\": {\"expected\": $exp_e, \"restored\": $got_e}"

    # 1. Catalog rows and per-label row counts must match exactly.
    if ! diff "$expected" "$tmp/got" > "$tmp/diff"; then
        GRAPH_ERROR="graph differs from $baseline: ag_label $got_labels/$exp_labels, vertices $got_v/$exp_v, edges $got_e/$exp_e; $(grep -E '^[<>]' "$tmp/diff" | head -5 | tr '\n' ';')"
        GRAPH_JSON+="}"
        rm -rf "$tmp"; return 1
    fi
    if [ ! -s "$tmp/got" ]; then
        GRAPH_JSON+=", \"cypher\": \"skipped (no graph)\"}"
        rm -rf "$tmp"; return 0
    fi

    # 2. Every label table in a graph's schema (the two base tables and their
    #    children) has its catalog row — no orphaned label tables. Other
    #    tables may share the schema (life_graph also holds app tables).
    got=$(psql_db "$db" "SELECT string_agg(g.name || ': ' || t.n || ' label tables vs ' || l.n || ' labels', '; ')
        FROM ag_catalog.ag_graph g,
             LATERAL (SELECT count(*) AS n FROM pg_class c
                      WHERE c.relnamespace = g.namespace AND c.relkind = 'r'
                        AND (c.relname IN ('_ag_label_vertex', '_ag_label_edge')
                             OR EXISTS (SELECT 1 FROM pg_inherits i JOIN pg_class p ON p.oid = i.inhparent
                                        WHERE i.inhrelid = c.oid AND p.relnamespace = g.namespace
                                          AND p.relname IN ('_ag_label_vertex', '_ag_label_edge')))) t,
             LATERAL (SELECT count(*) AS n FROM ag_catalog.ag_label x WHERE x.graph = g.graphid) l
        WHERE t.n <> l.n" 2>&1) || got="query failed: $got"
    if [ -n "$got" ]; then
        GRAPH_ERROR="graph schema/catalog mismatch: $got"
        GRAPH_JSON+="}"; rm -rf "$tmp"; return 1
    fi

    # 3. Sequences: the next id of every label (and the label-id sequence) must
    #    be above what is already used, or the first new vertex collides.
    got=$(psql_db "$db" "SELECT string_agg(bad, '; ') FROM (
        SELECT g.name || '.' || l.name || ' seq ' || s.last_value || ' < max ' || m.max_id AS bad
        FROM ag_catalog.ag_graph g JOIN ag_catalog.ag_label l ON l.graph = g.graphid,
        LATERAL (SELECT (xpath('/row/m/text()', query_to_xml(format(
            'SELECT coalesce(max(id::text::bigint & 281474976710655), 0) AS m FROM ONLY %s', l.relation),
            false, true, '')))[1]::text::bigint AS max_id) m,
        LATERAL (SELECT (xpath('/row/v/text()', query_to_xml(format(
            'SELECT last_value AS v FROM %s.%I', g.namespace, l.seq_name), false, true, '')))[1]::text::bigint AS last_value,
                        (xpath('/row/c/text()', query_to_xml(format(
            'SELECT is_called AS c FROM %s.%I', g.namespace, l.seq_name), false, true, '')))[1]::text::boolean AS is_called) s
        WHERE m.max_id > 0 AND (s.last_value < m.max_id OR (s.last_value = m.max_id AND NOT s.is_called))
        UNION ALL
        SELECT g.name || '._label_id_seq ' || s.v || ' < max label id ' || x.m
        FROM ag_catalog.ag_graph g,
        LATERAL (SELECT max(id::int) AS m FROM ag_catalog.ag_label WHERE graph = g.graphid) x,
        LATERAL (SELECT (xpath('/row/v/text()', query_to_xml(format(
            'SELECT last_value AS v FROM %s._label_id_seq', g.namespace), false, true, '')))[1]::text::bigint AS v) s
        WHERE s.v < x.m) q" 2>&1) || got="query failed: $got"
    if [ -n "$got" ]; then
        GRAPH_ERROR="graph sequences behind data: $got"
        GRAPH_JSON+="}"; rm -rf "$tmp"; return 1
    fi

    # 4. Cypher: MATCH on every label returns the expected count.
    local gname label kind pattern
    {
        echo "LOAD 'age';"
        echo "SET search_path = ag_catalog, \"\$user\", public;"
        while IFS='|' read -r gname label kind _; do
            [ "$label" = "-" ] && continue
            case "$gname$label" in *[\'\`\$]*) GRAPH_ERROR="unsupported graph/label name: $gname.$label"; break ;; esac
            if [ "$label" = "_ag_label_vertex" ]; then pattern="MATCH (n) RETURN count(n)"
            elif [ "$label" = "_ag_label_edge" ]; then pattern="MATCH ()-[n]->() RETURN count(n)"
            elif [ "$kind" = "v" ]; then pattern="MATCH (n:\`$label\`) RETURN count(n)"
            else pattern="MATCH ()-[n:\`$label\`]->() RETURN count(n)"
            fi
            echo "SELECT '$gname|$label|$kind|' || c::text FROM cypher('$gname', \$q\$ $pattern \$q\$) AS (c agtype);"
        done < "$expected"
    } > "$tmp/cypher.sql"
    if [ -n "$GRAPH_ERROR" ]; then GRAPH_JSON+="}"; rm -rf "$tmp"; return 1; fi
    if ! psql -h "$DB_HOST" -U "$DB_USER" -d "$db" -X -qAt -v ON_ERROR_STOP=1 \
            -f "$tmp/cypher.sql" > "$tmp/cypher.out" 2>&1; then
        GRAPH_ERROR="cypher query failed on restored copy: $(tail -c 300 "$tmp/cypher.out" | tr '\n' ' ')"
        GRAPH_JSON+=", \"cypher\": \"failed\"}"; rm -rf "$tmp"; return 1
    fi
    grep -v '|-|-|' "$expected" > "$tmp/exp_labels"
    if ! diff "$tmp/exp_labels" "$tmp/cypher.out" > "$tmp/cdiff"; then
        GRAPH_ERROR="cypher counts differ from $baseline: $(grep -E '^[<>]' "$tmp/cdiff" | head -5 | tr '\n' ';')"
        GRAPH_JSON+=", \"cypher\": \"mismatch\"}"; rm -rf "$tmp"; return 1
    fi
    GRAPH_JSON+=", \"cypher\": \"ok ($(wc -l < "$tmp/cypher.out") labels)\"}"
    rm -rf "$tmp"
    return 0
}
