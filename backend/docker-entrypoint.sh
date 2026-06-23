#!/bin/sh
set -e

# Fix ownership of the entire /data tree before dropping privileges.
# Bind mounts and named volumes are often created root-owned on the host.
chown -R appuser:appuser /data

# Ensure /data subdirs exist and are writable.
install -d -o appuser -g appuser -m 0755 \
    /data/journals /data/public /data/plugins

# Seed the example plugins (MeshCore + Meshtastic) into the plugins dir on first
# run, so a fresh install has working reference plugins to study / enable. Existing
# installs (non-empty /data/plugins) are left untouched.
if [ -d /app/examples/plugins ] && [ -z "$(ls -A /data/plugins 2>/dev/null)" ]; then
    cp -r /app/examples/plugins/. /data/plugins/
    chown -R appuser:appuser /data/plugins
fi

exec gosu appuser "$@"
