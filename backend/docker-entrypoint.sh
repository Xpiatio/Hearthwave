#!/bin/sh
set -e

# Fix ownership of the entire /data tree before dropping privileges.
# Bind mounts and named volumes are often created root-owned on the host.
chown -R appuser:appuser /data

# Ensure /data subdirs exist and are writable.
install -d -o appuser -g appuser -m 0755 \
    /data/voiceprints /data/journals /data/public

exec gosu appuser "$@"
