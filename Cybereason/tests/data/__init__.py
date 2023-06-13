import json

EPP_MALOP = json.load(open("tests/data/epp_malop.json"))
EPP_MALOP_DETAIL = json.load(open("tests/data/epp_malop_detail.json"))
EDR_MALOP = json.load(open("tests/data/edr_malop.json"))
EDR_MALOP_SUSPICIONS_RESULTS = json.load(open("tests/data/edr_malop_suspicions_result.json"))

LOGIN_HTML = open("tests/data/login.html", "rb").read()
APP_HTML = open("tests/data/app.html", "rb").read()
