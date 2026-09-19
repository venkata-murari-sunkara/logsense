EVENT_DESCRIPTIONS = {
    "E1": "a duplicate block add was attempted",
    "E2": "block verification succeeded",
    "E3": "a block was served to a client",
    "E4": "an exception occurred while serving a block",
    "E5": "the datanode started receiving a block",
    "E6": "a block was received successfully",
    "E7": "an exception occurred while writing a block",
    "E8": "a packet responder was interrupted",
    "E9": "a block was received from another node",
    "E10": "a packet responder threw an exception",
    "E11": "a packet responder terminated normally",
    "E12": "an exception occurred writing a block to a mirror node",
    "E13": "an empty packet was received for a block",
    "E14": "an exception occurred while receiving a block",
    "E15": "the block file offset was changed",
    "E16": "a block was transmitted to another node",
    "E17": "a block transfer failed",
    "E18": "a thread started to transfer a block",
    "E19": "a block was reopened",
    "E20": "an unexpected error occurred deleting a block, block info was missing",
    "E21": "a block file was deleted",
    "E22": "the namesystem allocated a new block",
    "E23": "the namesystem marked a block for deletion",
    "E24": "a block was removed from needed replications, it did not belong to any file",
    "E25": "a block replication was requested",
    "E26": "the block map was updated with a new stored block",
    "E27": "a redundant add-block request was received",
    "E28": "an add-block request was received for a block that does not belong to any file",
    "E29": "block replication monitoring timed out",
}


def describe_block(event_counts: dict) -> str:
    """
    Turn a block's event counts (e.g. {'E3': 2, 'E7': 1}) into a
    plain-English description of what happened to that block.
    Only mentions events that actually occurred (count > 0).
    """
    parts = []
    for event_id, count in event_counts.items():
        if count and count > 0 and event_id in EVENT_DESCRIPTIONS:
            desc = EVENT_DESCRIPTIONS[event_id]
            if count == 1:
                parts.append(desc)
            else:
                parts.append(f"{desc} ({count} times)")
    if not parts:
        return "No significant events recorded for this block."
    return "This block's history: " + "; ".join(parts) + "."