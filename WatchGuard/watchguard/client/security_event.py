import enum


# 1 — Malware
# 2 — PUPs (Potentially Unwanted Programs)
# 3 — Blocked Programs
# 4 — Exploits
# 5 — Blocked by Advanced Security Policies
# 6 — Virus
# 7 — Spyware
# 8 — Hacking Tools and PUPs Detected by Antivirus
# 9 — Phishing
# 10 — Suspicious
# 11 — Dangerous Actions
# 12 — Tracking Cookies
# 13 — Malware URLs
# 14 — Other Security Event Detected by Antivirus
# 15 — Intrusion Attempts
# 16 — Blocked Connections
# 17 — Blocked Devices
# 18 — Indicators of Attack
# 19 — Network Attack Protection
class SecurityEvent(enum.Enum):
    MALWARE = 1
    PUPS = 2
    BLOCKED_PROGRAMS = 3
    EXPLOITS = 4
    ADVANCED_SECURITY_POLICIES = 5
    VIRUS = 6
    SPYWARE = 7
    HACKING_TOOLS_AND_PUPS = 8
    PHISHING = 9
    SUSPICIOUS = 10
    DANGEROUS_ACTIONS = 11
    TRACKING_COOKIES = 12
    MALWARE_URLS = 13
    OTHER_SECURITY_EVENT = 14
    INTRUSION_ATTEMPTS = 15
    BLOCKED_CONNECTIONS = 16
    BLOCKED_DEVICES = 17
    INDICATORS_OF_ATTACK = 18
    NETWORK_ATTACK_PROTECTION = 19
