from backend.constants import SERVICE_FRS, SERVICE_GMRS
from backend.text.callsigns import callsign_to_nato
from backend.text.locations import expand_trailing_state

ID_INTERVAL_SECONDS = 15 * 60  # FCC Part 95: identify at least every 15 minutes when in use.


def format_tail_id(my_call: str, my_name: str = "") -> str:
    """Return the short tail-ID appended to every untargeted GMRS transmission:
    the call sign, followed by the operator's name when one is set."""
    name = (my_name or "").strip()
    return f"{my_call} {name}." if name else f"{my_call}."


def format_outgoing_message(
    text,
    target_call,
    target_name,
    my_call,
    my_name,
    now,
    service=SERVICE_GMRS,
):
    """Format an outgoing TX message per FCC Part 95 station-ID rules.

    Returns (spoken_text, new_last_id_time).

    Three cases:
      • Targeted GMRS: emit 'calling' preface containing both callsigns.
        Satisfies FCC ID; no tail appended.
      • Untargeted GMRS: emit body then append short tail ID (call sign only)
        on every transmission. new_last_id_time is always `now`.
      • FRS: speak body verbatim, no callsign framing. Returns None for
        new_last_id_time so the caller can preserve the GMRS timer.
    """
    if service == SERVICE_FRS:
        return text, None

    prefaced = bool(target_call and target_call.upper() != "ALL")

    if prefaced:
        clean_name = (target_name or "").strip()
        target_label = f"{target_call} {clean_name}" if clean_name else target_call
        if text:
            spoken_text = f"{my_call} {my_name} calling {target_label}. {text}"
        else:
            spoken_text = f"{my_call} {my_name} calling {target_label}."
        return spoken_text, now

    tail = format_tail_id(my_call, my_name)
    spoken_text = f"{text}. {tail}" if text else tail
    return spoken_text, now


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
