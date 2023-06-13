from sekoia_automation.action import Action


def virustotal_detection_outputs(action: Action, vt_response: dict, threshold: int = 1):
    # Branch "detected" activated if more than "detect_trehsold" positives are returned from VirusTotal
    if vt_response.get("positives", 0) >= threshold:
        action.set_output("detected", True)

    else:
        action.set_output("not detected", True)
