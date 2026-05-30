from backend.constants import SERVICE_FRS, SERVICE_GMRS
from backend.text.callsigns import callsign_to_nato
from backend.text.locations import expand_trailing_state

ID_INTERVAL_SECONDS = 15 * 60  # FCC Part 95: identify at least every 15 minutes when in use.


def format_outgoing_message(
    text,
    target_call,
    target_name,
    my_call,
    my_name,
    last_id_time,
    now,
    id_interval_seconds=ID_INTERVAL_SECONDS,
    service=SERVICE_GMRS,
):
    """Format an outgoing TX message per FCC Part 95 station-ID rules.

    Returns (spoken_text, new_last_id_time). The caller is expected to persist
    new_last_id_time on its own state so subsequent calls can apply the
    15-minute rule consistently.

    Three cases:
      • Targeted GMRS (`target_call` is set and not "ALL", service is GMRS):
        emit a 'calling' preface that contains both operator callsigns; that
        preface satisfies the FCC ID requirement on its own. Empty body text
        is permitted — the preface itself is the call.
      • Untargeted GMRS (target is "ALL" or empty, service is GMRS): emit the
        user's text verbatim; append "This is <call> <name>." if more than
        `id_interval_seconds` has elapsed since the last identification (or if
        we have never identified).
      • FRS (service == SERVICE_FRS): speak the body verbatim with no callsign
        framing — Part 95 Subpart B doesn't require station ID. last_id_time
        is returned untouched so a mid-session toggle back to GMRS doesn't
        skip the next ID.
    """
    if service == SERVICE_FRS:
        return text, last_id_time

    prefaced = bool(target_call and target_call.upper() != "ALL")

    if prefaced:
        clean_name = (target_name or "").strip()
        target_label = f"{target_call} {clean_name}" if clean_name else target_call
        if text:
            spoken_text = f"{my_call} {my_name} calling {target_label}. {text}"
        else:
            spoken_text = f"{my_call} {my_name} calling {target_label}."
        return spoken_text, now

    spoken_text = text
    if last_id_time is None or (now - last_id_time).total_seconds() > id_interval_seconds:
        spoken_text += f". This is {my_call} {my_name}."
        return spoken_text, now
    return spoken_text, last_id_time


def format_standalone_id(my_call, my_name, my_location, now):
    """Format a standalone station ID for the 'This is' button.

    Output shape: `This is <CALL>, <NATO phonetic CALL>. <name> [from <location>].`

    Returns (spoken_text, new_last_id_time). The caller persists the timestamp
    so the 15-minute rule resets on a standalone ID send.
    """
    nato_call = callsign_to_nato(my_call)
    location = expand_trailing_state((my_location or "").strip())
    if location:
        spoken_text = f"This is {my_call}, {nato_call}. {my_name} from {location}."
    else:
        spoken_text = f"This is {my_call}, {nato_call}. {my_name}."
    return spoken_text, now
