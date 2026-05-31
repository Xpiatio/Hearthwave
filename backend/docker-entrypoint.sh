#!/bin/sh
set -e

# Ensure /data subdirs exist and are writable.
# Named Docker volumes are created root-owned; fix ownership before dropping privileges.
install -d -o appuser -g appuser -m 0755 \
    /data/voiceprints /data/journals /data/public

exec gosu appuser "$@"
