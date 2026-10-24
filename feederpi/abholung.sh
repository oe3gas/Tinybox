#!/bin/sh
# Feeder-Pi: the only command the PC may run over SSH (user "abholer").
# Installed as /usr/local/lib/feederpi/abholung.sh (root-owned); forced by authorized_keys
# (command=...,restrict) and by sshd (ForceCommand), whatever the PC asks for.
#
#   list               names of the finished bulletin files (*.txt) in the outbox
#   bundle             all finished *.txt files as a tar stream on stdout
#   ack NAME [NAME..]  mark as fetched: move to abgeholt/ (cleaned after 2 days)
#
# The jobs write NAME.tmp first and rename it to NAME.txt, so a .txt file is
# always complete. Only plain file names are accepted, never paths.
set -eu
set -f                                   # no globbing of the client's words

OUTBOX=/run/tinybox/ausgang
DONE=$OUTBOX/abgeholt

# shellcheck disable=SC2086              # split into words on purpose
set -- ${SSH_ORIGINAL_COMMAND:-}
cmd=${1:-}
[ $# -gt 0 ] && shift

ok_name() {
    case $1 in
        ''|.*|*[!A-Za-z0-9._-]*) return 1 ;;
        *.txt) [ -f "$OUTBOX/$1" ] && [ ! -L "$OUTBOX/$1" ] ;;
        *) return 1 ;;
    esac
}

finished() {                             # finished files, one per line
    set +f
    for f in "$OUTBOX"/*.txt; do
        n=${f##*/}
        ok_name "$n" && printf '%s\n' "$n"
    done
    set -f
}

cd "$OUTBOX"
case $cmd in
    list)
        finished
        ;;
    bundle)
        names=$(finished)
        [ -n "$names" ] || exit 0          # nothing to fetch: empty output
        # shellcheck disable=SC2086
        tar -cf - -- $names
        ;;
    ack)
        mkdir -p "$DONE"
        for n in "$@"; do
            if ok_name "$n"; then
                mv -f -- "$n" "$DONE/$n"
            fi
        done
        ;;
    *)
        echo "abholung: allowed commands: list | bundle | ack NAME..." >&2
        exit 2
        ;;
esac
