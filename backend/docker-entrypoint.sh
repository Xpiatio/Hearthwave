#!/bin/sh
set -e

# Fix ownership of the entire /data tree before dropping privileges.
# Bind mounts and named volumes are often created root-owned on the host.
chown -R appuser:appuser /data

# Ensure /data subdirs exist and are writable.
install -d -o appuser -g appuser -m 0755 \
    /data/journals /data/public /data/plugins

# Seed / refresh the example plugins (MeshCore + Meshtastic) in the plugins dir, so
# a fresh install has working reference plugins to study, and an upgraded install
# picks up fixes we ship to them instead of running last release's copy forever.
#
# An operator may edit a seeded plugin in place, and that edit must survive an
# upgrade. So we record the hash of every file we write in .hearthwave-seeded: on a
# later run a plugin is refreshed only when it still matches what we last seeded.
# Anything else — an edited plugin, or a pre-existing install from before this
# marker existed — is left alone and logged.
SEED_STATE=/data/plugins/.hearthwave-seeded

_plugin_hash() {
    sha256sum "$1" 2>/dev/null | cut -d' ' -f1
}

_seeded_hash() {
    [ -f "$SEED_STATE" ] || return 0
    awk -v id="$1" '$1 == id { print $2 }' "$SEED_STATE"
}

if [ -d /app/examples/plugins ]; then
    : > "$SEED_STATE.new"
    for src in /app/examples/plugins/*/; do
        [ -f "${src}plugin.py" ] || continue
        id=$(basename "$src")
        dest="/data/plugins/$id"
        shipped=$(_plugin_hash "${src}plugin.py")

        # Only a copy this image wrote gets recorded. A plugin we left alone stays
        # unrecorded, so it is never mistaken for ours on the next upgrade.
        record=y
        if [ ! -d "$dest" ]; then
            cp -r "$src" /data/plugins/
            echo "hearthwave: seeded example plugin $id"
        else
            installed=$(_plugin_hash "$dest/plugin.py")
            if [ "$installed" != "$shipped" ]; then
                if [ "$installed" = "$(_seeded_hash "$id")" ]; then
                    cp -r "${src}." "$dest/"
                    echo "hearthwave: refreshed example plugin $id"
                else
                    record=n
                    echo "hearthwave: example plugin $id differs from the shipped copy — keeping yours"
                fi
            fi
        fi

        if [ "$record" = y ]; then
            echo "$id $shipped" >> "$SEED_STATE.new"
        fi
    done
    mv "$SEED_STATE.new" "$SEED_STATE"
    chown -R appuser:appuser /data/plugins
fi

exec gosu appuser "$@"
