PRIMARY_CUSTOMER = {
    "name": "John Doe",
    "gsnumber": "22",
    "private_ip": "1.2.3.4",
    "public_ip": "4.3.2.1:61606",
    "hostname": "workstation.test.local",
    "os": "Windows Server 2022 Datacenter Azure Edition (21H2)",
}
PRIMARY_REP = {
    "name": "Admin",
    "gsnumber": "21",
    "public_ip": "[2001:db8::1]:56722",
}
SESSION_HEADER = {
    "session_id": "e9e99aeb9ad54fb381634498502c5a1b",
    "jump_group": {"name": "EXAMPLE_JUMP_GROUP", "type": "shared"},
    "primary_customer": PRIMARY_CUSTOMER,
    "primary_rep": PRIMARY_REP,
    "file_transfer_count": "2",
    "file_move_count": "0",
    "file_delete_count": "1",
}
EXPECTED_SESSION_EVENTS = [
    {
        "timestamp": "1733239565",
        "event_type": "Session Start",
        **SESSION_HEADER,
    },
    {
        "timestamp": "1733239565",
        "event_type": "Conference Owner Changed",
        "performed_by": {
            "type": "representative",
            "name": "Admin",
            "gsnumber": "21",
            "public_ip": "[2001:db8::1]:56722",
        },
        "data": {"owner": "Pre-start Conference"},
        "destination": {"type": "system", "name": "Pre-start Conference", "gsnumber": "0"},
        **SESSION_HEADER,
    },
    {
        "timestamp": "1733239600",
        "event_type": "Conference Member Added",
        "performed_by": {
            "type": "customer",
            "name": "John Doe",
            "gsnumber": "22",
            "private_ip": "1.2.3.4",
            "public_ip": "4.3.2.1:61606",
            "hostname": "workstation.test.local",
            "os": "Windows Server 2022 Datacenter Azure Edition (21H2)",
        },
        **SESSION_HEADER,
    },
]
