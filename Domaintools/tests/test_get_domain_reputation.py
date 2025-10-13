from typing import Any
import requests_mock

from domaintools.get_domain_reputation import DomaintoolsDomainReputation

DOMAIN: str = "google.com"

DT_OUTPUT: dict[str, Any] = {
  "results": [
    {
      "domain": "google.com",
      "whois_url": "https://whois.domaintools.com/google.com",
      "adsense": {
        "value": "",
        "count": 0
      },
      "alexa": 1,
      "popularity_rank": 1,
      "active": true,
      "google_analytics": {
        "value": "",
        "count": 0
      },
      "ga4": [],
      "gtm_codes": [],
      "fb_codes": [],
      "hotjar_codes": [],
      "baidu_codes": [],
      "yandex_codes": [],
      "matomo_codes": [],
      "statcounter_project_codes": [],
      "statcounter_security_codes": [],
      "admin_contact": {
        "name": {
          "value": "",
          "count": 0
        },
        "org": {
          "value": "",
          "count": 0
        },
        "street": {
          "value": "",
          "count": 0
        },
        "city": {
          "value": "",
          "count": 0
        },
        "state": {
          "value": "",
          "count": 0
        },
        "postal": {
          "value": "",
          "count": 0
        },
        "country": {
          "value": "",
          "count": 0
        },
        "phone": {
          "value": "",
          "count": 0
        },
        "fax": {
          "value": "",
          "count": 0
        },
        "email": [
          {
            "value": "select request email form at https://domains.markmonitor.com/whois/google.com",
            "count": 1
          }
        ]
      },
      "billing_contact": {
        "name": {
          "value": "",
          "count": 0
        },
        "org": {
          "value": "",
          "count": 0
        },
        "street": {
          "value": "",
          "count": 0
        },
        "city": {
          "value": "",
          "count": 0
        },
        "state": {
          "value": "",
          "count": 0
        },
        "postal": {
          "value": "",
          "count": 0
        },
        "country": {
          "value": "",
          "count": 0
        },
        "phone": {
          "value": "",
          "count": 0
        },
        "fax": {
          "value": "",
          "count": 0
        },
        "email": []
      },
      "registrant_contact": {
        "name": {
          "value": "",
          "count": 0
        },
        "org": {
          "value": "Google LLC",
          "count": 24177
        },
        "street": {
          "value": "",
          "count": 0
        },
        "city": {
          "value": "",
          "count": 0
        },
        "state": {
          "value": "",
          "count": 0
        },
        "postal": {
          "value": "",
          "count": 0
        },
        "country": {
          "value": "us",
          "count": 296618199
        },
        "phone": {
          "value": "",
          "count": 0
        },
        "fax": {
          "value": "",
          "count": 0
        },
        "email": [
          {
            "value": "select request email form at https://domains.markmonitor.com/whois/google.com",
            "count": 1
          }
        ]
      },
      "technical_contact": {
        "name": {
          "value": "",
          "count": 0
        },
        "org": {
          "value": "",
          "count": 0
        },
        "street": {
          "value": "",
          "count": 0
        },
        "city": {
          "value": "",
          "count": 0
        },
        "state": {
          "value": "",
          "count": 0
        },
        "postal": {
          "value": "",
          "count": 0
        },
        "country": {
          "value": "",
          "count": 0
        },
        "phone": {
          "value": "",
          "count": 0
        },
        "fax": {
          "value": "",
          "count": 0
        },
        "email": [
          {
            "value": "select request email form at https://domains.markmonitor.com/whois/google.com",
            "count": 1
          }
        ]
      },
      "create_date": {
        "value": "1997-09-15",
        "count": 1728
      },
      "expiration_date": {
        "value": "2028-09-14",
        "count": 22273
      },
      "email_domain": [
        {
          "value": "markmonitor.com",
          "count": 1765164
        },
        {
          "value": "google.com",
          "count": 22976033
        }
      ],
      "soa_email": [
        {
          "value": "dns-admin@google.com",
          "count": 174118
        }
      ],
      "ssl_email": [],
      "additional_whois_email": [
        {
          "value": "abusecomplaints@markmonitor.com",
          "count": 1459577
        },
        {
          "value": "whoisrequest@markmonitor.com",
          "count": 712320
        }
      ],
      "ip": [
        {
          "address": {
            "value": "142.250.73.110",
            "count": 943
          },
          "asn": [
            {
              "value": 15169,
              "count": 35129699
            }
          ],
          "country_code": {
            "value": "us",
            "count": 190985230
          },
          "isp": {
            "value": "Google",
            "count": 52952375
          }
        },
        {
          "address": {
            "value": "142.250.217.68",
            "count": 261
          },
          "asn": [
            {
              "value": 15169,
              "count": 35129699
            }
          ],
          "country_code": {
            "value": "us",
            "count": 190985230
          },
          "isp": {
            "value": "Google",
            "count": 52952375
          }
        }
      ],
      "mx": [
        {
          "host": {
            "value": "smtp.google.com",
            "count": 4578220
          },
          "domain": {
            "value": "google.com",
            "count": 34846786
          },
          "ip": [
            {
              "value": "173.194.203.27",
              "count": 1736657
            },
            {
              "value": "74.125.199.27",
              "count": 1673147
            },
            {
              "value": "74.125.142.26",
              "count": 2990141
            },
            {
              "value": "74.125.142.27",
              "count": 2871561
            },
            {
              "value": "74.125.199.26",
              "count": 1685661
            }
          ],
          "priority": 10
        }
      ],
      "name_server": [
        {
          "host": {
            "value": "ns1.google.com",
            "count": 10981
          },
          "domain": {
            "value": "google.com",
            "count": 15687
          },
          "ip": [
            {
              "value": "216.239.32.10",
              "count": 9003
            }
          ]
        },
        {
          "host": {
            "value": "ns2.google.com",
            "count": 10818
          },
          "domain": {
            "value": "google.com",
            "count": 15687
          },
          "ip": [
            {
              "value": "216.239.34.10",
              "count": 8786
            }
          ]
        },
        {
          "host": {
            "value": "ns3.google.com",
            "count": 6999
          },
          "domain": {
            "value": "google.com",
            "count": 15687
          },
          "ip": [
            {
              "value": "216.239.36.10",
              "count": 6911
            }
          ]
        },
        {
          "host": {
            "value": "ns4.google.com",
            "count": 6941
          },
          "domain": {
            "value": "google.com",
            "count": 15687
          },
          "ip": [
            {
              "value": "216.239.38.10",
              "count": 6871
            }
          ]
        }
      ],
      "domain_risk": {
        "risk_score": 0,
        "components": [
          {
            "name": "zerolist",
            "risk_score": 0
          }
        ]
      },
      "redirect": {
        "value": "",
        "count": 0
      },
      "redirect_domain": {
        "value": "",
        "count": 0
      },
      "registrant_name": {
        "value": "",
        "count": 0
      },
      "registrant_org": {
        "value": "Google LLC",
        "count": 25938
      },
      "registrar": {
        "value": "MarkMonitor, Inc.",
        "count": 737150
      },
      "registrar_status": [
        "clientdeleteprohibited",
        "clienttransferprohibited",
        "clientupdateprohibited",
        "serverdeleteprohibited",
        "servertransferprohibited",
        "serverupdateprohibited"
      ],
      "spf_info": "",
      "ssl_info": [
        {
          "hash": {
            "value": "134a0b81a8a437a9d731cbdda67653218a1b2e0c",
            "count": 39
          },
          "subject": {
            "value": "CN=*.google.com",
            "count": 1253
          },
          "organization": {
            "value": "",
            "count": 0
          },
          "email": [],
          "alt_names": [
            {
              "value": "*.google.com",
              "count": 0
            },
            {
              "value": "*.appengine.google.com",
              "count": 0
            },
            {
              "value": "*.bdn.dev",
              "count": 0
            },
            {
              "value": "*.origin-test.bdn.dev",
              "count": 0
            },
            {
              "value": "*.cloud.google.com",
              "count": 0
            },
            {
              "value": "*.crowdsource.google.com",
              "count": 0
            },
            {
              "value": "*.datacompute.google.com",
              "count": 0
            },
            {
              "value": "*.google.ca",
              "count": 0
            },
            {
              "value": "*.google.cl",
              "count": 0
            },
            {
              "value": "*.google.co.in",
              "count": 0
            },
            {
              "value": "*.google.co.jp",
              "count": 0
            },
            {
              "value": "*.google.co.uk",
              "count": 0
            },
            {
              "value": "*.google.com.ar",
              "count": 0
            },
            {
              "value": "*.google.com.au",
              "count": 0
            },
            {
              "value": "*.google.com.br",
              "count": 0
            },
            {
              "value": "*.google.com.co",
              "count": 0
            },
            {
              "value": "*.google.com.mx",
              "count": 0
            },
            {
              "value": "*.google.com.tr",
              "count": 0
            },
            {
              "value": "*.google.com.vn",
              "count": 0
            },
            {
              "value": "*.google.de",
              "count": 0
            },
            {
              "value": "*.google.es",
              "count": 0
            },
            {
              "value": "*.google.fr",
              "count": 0
            },
            {
              "value": "*.google.hu",
              "count": 0
            },
            {
              "value": "*.google.it",
              "count": 0
            },
            {
              "value": "*.google.nl",
              "count": 0
            },
            {
              "value": "*.google.pl",
              "count": 0
            },
            {
              "value": "*.google.pt",
              "count": 0
            },
            {
              "value": "*.googleapis.cn",
              "count": 0
            },
            {
              "value": "*.googlevideo.com",
              "count": 0
            },
            {
              "value": "*.gstatic.cn",
              "count": 0
            },
            {
              "value": "*.gstatic-cn.com",
              "count": 0
            },
            {
              "value": "googlecnapps.cn",
              "count": 0
            },
            {
              "value": "*.googlecnapps.cn",
              "count": 0
            },
            {
              "value": "googleapps-cn.com",
              "count": 0
            },
            {
              "value": "*.googleapps-cn.com",
              "count": 0
            },
            {
              "value": "gkecnapps.cn",
              "count": 0
            },
            {
              "value": "*.gkecnapps.cn",
              "count": 0
            },
            {
              "value": "googledownloads.cn",
              "count": 0
            },
            {
              "value": "*.googledownloads.cn",
              "count": 0
            },
            {
              "value": "recaptcha.net.cn",
              "count": 0
            },
            {
              "value": "*.recaptcha.net.cn",
              "count": 0
            },
            {
              "value": "recaptcha-cn.net",
              "count": 0
            },
            {
              "value": "*.recaptcha-cn.net",
              "count": 0
            },
            {
              "value": "widevine.cn",
              "count": 0
            },
            {
              "value": "*.widevine.cn",
              "count": 0
            },
            {
              "value": "ampproject.org.cn",
              "count": 0
            },
            {
              "value": "*.ampproject.org.cn",
              "count": 0
            },
            {
              "value": "ampproject.net.cn",
              "count": 0
            },
            {
              "value": "*.ampproject.net.cn",
              "count": 0
            },
            {
              "value": "google-analytics-cn.com",
              "count": 0
            },
            {
              "value": "*.google-analytics-cn.com",
              "count": 0
            },
            {
              "value": "googleadservices-cn.com",
              "count": 0
            },
            {
              "value": "*.googleadservices-cn.com",
              "count": 0
            },
            {
              "value": "googlevads-cn.com",
              "count": 0
            },
            {
              "value": "*.googlevads-cn.com",
              "count": 0
            },
            {
              "value": "googleapis-cn.com",
              "count": 0
            },
            {
              "value": "*.googleapis-cn.com",
              "count": 0
            },
            {
              "value": "googleoptimize-cn.com",
              "count": 0
            },
            {
              "value": "*.googleoptimize-cn.com",
              "count": 0
            },
            {
              "value": "doubleclick-cn.net",
              "count": 0
            },
            {
              "value": "*.doubleclick-cn.net",
              "count": 0
            },
            {
              "value": "*.fls.doubleclick-cn.net",
              "count": 0
            },
            {
              "value": "*.g.doubleclick-cn.net",
              "count": 0
            },
            {
              "value": "doubleclick.cn",
              "count": 0
            },
            {
              "value": "*.doubleclick.cn",
              "count": 0
            },
            {
              "value": "*.fls.doubleclick.cn",
              "count": 0
            },
            {
              "value": "*.g.doubleclick.cn",
              "count": 0
            },
            {
              "value": "dartsearch-cn.net",
              "count": 0
            },
            {
              "value": "*.dartsearch-cn.net",
              "count": 0
            },
            {
              "value": "googletraveladservices-cn.com",
              "count": 0
            },
            {
              "value": "*.googletraveladservices-cn.com",
              "count": 0
            },
            {
              "value": "googletagservices-cn.com",
              "count": 0
            },
            {
              "value": "*.googletagservices-cn.com",
              "count": 0
            },
            {
              "value": "googletagmanager-cn.com",
              "count": 0
            },
            {
              "value": "*.googletagmanager-cn.com",
              "count": 0
            },
            {
              "value": "googlesyndication-cn.com",
              "count": 0
            },
            {
              "value": "*.googlesyndication-cn.com",
              "count": 0
            },
            {
              "value": "*.safeframe.googlesyndication-cn.com",
              "count": 0
            },
            {
              "value": "app-measurement-cn.com",
              "count": 0
            },
            {
              "value": "*.app-measurement-cn.com",
              "count": 0
            },
            {
              "value": "gvt1-cn.com",
              "count": 0
            },
            {
              "value": "*.gvt1-cn.com",
              "count": 0
            },
            {
              "value": "gvt2-cn.com",
              "count": 0
            },
            {
              "value": "*.gvt2-cn.com",
              "count": 0
            },
            {
              "value": "2mdn-cn.net",
              "count": 0
            },
            {
              "value": "*.2mdn-cn.net",
              "count": 0
            },
            {
              "value": "googleflights-cn.net",
              "count": 0
            },
            {
              "value": "*.googleflights-cn.net",
              "count": 0
            },
            {
              "value": "admob-cn.com",
              "count": 0
            },
            {
              "value": "*.admob-cn.com",
              "count": 0
            },
            {
              "value": "*.gemini.cloud.google.com",
              "count": 0
            },
            {
              "value": "googlesandbox-cn.com",
              "count": 0
            },
            {
              "value": "*.googlesandbox-cn.com",
              "count": 0
            },
            {
              "value": "*.safenup.googlesandbox-cn.com",
              "count": 0
            },
            {
              "value": "*.gstatic.com",
              "count": 0
            },
            {
              "value": "*.metric.gstatic.com",
              "count": 0
            },
            {
              "value": "*.gvt1.com",
              "count": 0
            },
            {
              "value": "*.gcpcdn.gvt1.com",
              "count": 0
            },
            {
              "value": "*.gvt2.com",
              "count": 0
            },
            {
              "value": "*.gcp.gvt2.com",
              "count": 0
            },
            {
              "value": "*.url.google.com",
              "count": 0
            },
            {
              "value": "*.youtube-nocookie.com",
              "count": 0
            },
            {
              "value": "*.ytimg.com",
              "count": 0
            },
            {
              "value": "ai.android",
              "count": 0
            },
            {
              "value": "android.com",
              "count": 0
            },
            {
              "value": "*.android.com",
              "count": 0
            },
            {
              "value": "*.flash.android.com",
              "count": 0
            },
            {
              "value": "g.cn",
              "count": 0
            },
            {
              "value": "*.g.cn",
              "count": 0
            },
            {
              "value": "g.co",
              "count": 0
            },
            {
              "value": "*.g.co",
              "count": 0
            },
            {
              "value": "goo.gl",
              "count": 0
            },
            {
              "value": "www.goo.gl",
              "count": 0
            },
            {
              "value": "google-analytics.com",
              "count": 0
            },
            {
              "value": "*.google-analytics.com",
              "count": 0
            },
            {
              "value": "google.com",
              "count": 0
            },
            {
              "value": "googlecommerce.com",
              "count": 0
            },
            {
              "value": "*.googlecommerce.com",
              "count": 0
            },
            {
              "value": "ggpht.cn",
              "count": 0
            },
            {
              "value": "*.ggpht.cn",
              "count": 0
            },
            {
              "value": "urchin.com",
              "count": 0
            },
            {
              "value": "*.urchin.com",
              "count": 0
            },
            {
              "value": "youtu.be",
              "count": 0
            },
            {
              "value": "youtube.com",
              "count": 0
            },
            {
              "value": "*.youtube.com",
              "count": 0
            },
            {
              "value": "music.youtube.com",
              "count": 0
            },
            {
              "value": "*.music.youtube.com",
              "count": 0
            },
            {
              "value": "youtubeeducation.com",
              "count": 0
            },
            {
              "value": "*.youtubeeducation.com",
              "count": 0
            },
            {
              "value": "youtubekids.com",
              "count": 0
            },
            {
              "value": "*.youtubekids.com",
              "count": 0
            },
            {
              "value": "yt.be",
              "count": 0
            },
            {
              "value": "*.yt.be",
              "count": 0
            },
            {
              "value": "android.clients.google.com",
              "count": 0
            },
            {
              "value": "*.android.google.cn",
              "count": 0
            },
            {
              "value": "*.chrome.google.cn",
              "count": 0
            },
            {
              "value": "*.developers.google.cn",
              "count": 0
            },
            {
              "value": "*.aistudio.google.com",
              "count": 0
            }
          ],
          "sources": {
            "active": 1759141202000
          },
          "common_name": {
            "value": "*.google.com",
            "count": 1257
          },
          "issuer_common_name": {
            "value": "WR2",
            "count": 2028
          },
          "not_after": {
            "value": 20251201,
            "count": 2962561
          },
          "not_before": {
            "value": 20250908,
            "count": 3630817
          },
          "duration": {
            "value": 84,
            "count": 1024089
          }
        },
        {
          "hash": {
            "value": "281ce795ec8d329e639a72b28d47e513f7ca5e18",
            "count": 1
          },
          "subject": {
            "value": "CN=www.google.com",
            "count": 193
          },
          "organization": {
            "value": "",
            "count": 0
          },
          "email": [],
          "alt_names": [
            {
              "value": "www.google.com",
              "count": 0
            }
          ],
          "sources": {
            "active": 1759141202000
          },
          "common_name": {
            "value": "www.google.com",
            "count": 1105
          },
          "issuer_common_name": {
            "value": "WR2",
            "count": 2028
          },
          "not_after": {
            "value": 20251201,
            "count": 2962561
          },
          "not_before": {
            "value": 20250908,
            "count": 3630817
          },
          "duration": {
            "value": 84,
            "count": 1024089
          }
        },
        {
          "hash": {
            "value": "a440f4ddc0866369fca70cb3c808fdddccdd89fb",
            "count": 272
          },
          "subject": {
            "value": "CN=google.com",
            "count": 329
          },
          "organization": {
            "value": "",
            "count": 0
          },
          "email": [],
          "alt_names": [
            {
              "value": "google.com",
              "count": 0
            },
            {
              "value": "*.appengine.google.com",
              "count": 0
            },
            {
              "value": "*.bdn.dev",
              "count": 0
            },
            {
              "value": "*.origin-test.bdn.dev",
              "count": 0
            },
            {
              "value": "*.cloud.google.com",
              "count": 0
            },
            {
              "value": "*.crowdsource.google.com",
              "count": 0
            },
            {
              "value": "*.datacompute.google.com",
              "count": 0
            },
            {
              "value": "*.google.ca",
              "count": 0
            },
            {
              "value": "*.google.cl",
              "count": 0
            },
            {
              "value": "*.google.co.in",
              "count": 0
            },
            {
              "value": "*.google.co.jp",
              "count": 0
            },
            {
              "value": "*.google.co.uk",
              "count": 0
            },
            {
              "value": "*.google.com.ar",
              "count": 0
            },
            {
              "value": "*.google.com.au",
              "count": 0
            },
            {
              "value": "*.google.com.br",
              "count": 0
            },
            {
              "value": "*.google.com.co",
              "count": 0
            },
            {
              "value": "*.google.com.mx",
              "count": 0
            },
            {
              "value": "*.google.com.tr",
              "count": 0
            },
            {
              "value": "*.google.com.vn",
              "count": 0
            },
            {
              "value": "*.google.de",
              "count": 0
            },
            {
              "value": "*.google.es",
              "count": 0
            },
            {
              "value": "*.google.fr",
              "count": 0
            },
            {
              "value": "*.google.hu",
              "count": 0
            },
            {
              "value": "*.google.it",
              "count": 0
            },
            {
              "value": "*.google.nl",
              "count": 0
            },
            {
              "value": "*.google.pl",
              "count": 0
            },
            {
              "value": "*.google.pt",
              "count": 0
            },
            {
              "value": "*.googleapis.cn",
              "count": 0
            },
            {
              "value": "*.googlevideo.com",
              "count": 0
            },
            {
              "value": "*.gstatic.cn",
              "count": 0
            },
            {
              "value": "*.gstatic-cn.com",
              "count": 0
            },
            {
              "value": "googlecnapps.cn",
              "count": 0
            },
            {
              "value": "*.googlecnapps.cn",
              "count": 0
            },
            {
              "value": "googleapps-cn.com",
              "count": 0
            },
            {
              "value": "*.googleapps-cn.com",
              "count": 0
            },
            {
              "value": "gkecnapps.cn",
              "count": 0
            },
            {
              "value": "*.gkecnapps.cn",
              "count": 0
            },
            {
              "value": "googledownloads.cn",
              "count": 0
            },
            {
              "value": "*.googledownloads.cn",
              "count": 0
            },
            {
              "value": "recaptcha.net.cn",
              "count": 0
            },
            {
              "value": "*.recaptcha.net.cn",
              "count": 0
            },
            {
              "value": "recaptcha-cn.net",
              "count": 0
            },
            {
              "value": "*.recaptcha-cn.net",
              "count": 0
            },
            {
              "value": "widevine.cn",
              "count": 0
            },
            {
              "value": "*.widevine.cn",
              "count": 0
            },
            {
              "value": "ampproject.org.cn",
              "count": 0
            },
            {
              "value": "*.ampproject.org.cn",
              "count": 0
            },
            {
              "value": "ampproject.net.cn",
              "count": 0
            },
            {
              "value": "*.ampproject.net.cn",
              "count": 0
            },
            {
              "value": "google-analytics-cn.com",
              "count": 0
            },
            {
              "value": "*.google-analytics-cn.com",
              "count": 0
            },
            {
              "value": "googleadservices-cn.com",
              "count": 0
            },
            {
              "value": "*.googleadservices-cn.com",
              "count": 0
            },
            {
              "value": "googlevads-cn.com",
              "count": 0
            },
            {
              "value": "*.googlevads-cn.com",
              "count": 0
            },
            {
              "value": "googleapis-cn.com",
              "count": 0
            },
            {
              "value": "*.googleapis-cn.com",
              "count": 0
            },
            {
              "value": "googleoptimize-cn.com",
              "count": 0
            },
            {
              "value": "*.googleoptimize-cn.com",
              "count": 0
            },
            {
              "value": "doubleclick-cn.net",
              "count": 0
            },
            {
              "value": "*.doubleclick-cn.net",
              "count": 0
            },
            {
              "value": "*.fls.doubleclick-cn.net",
              "count": 0
            },
            {
              "value": "*.g.doubleclick-cn.net",
              "count": 0
            },
            {
              "value": "doubleclick.cn",
              "count": 0
            },
            {
              "value": "*.doubleclick.cn",
              "count": 0
            },
            {
              "value": "*.fls.doubleclick.cn",
              "count": 0
            },
            {
              "value": "*.g.doubleclick.cn",
              "count": 0
            },
            {
              "value": "dartsearch-cn.net",
              "count": 0
            },
            {
              "value": "*.dartsearch-cn.net",
              "count": 0
            },
            {
              "value": "googletraveladservices-cn.com",
              "count": 0
            },
            {
              "value": "*.googletraveladservices-cn.com",
              "count": 0
            },
            {
              "value": "googletagservices-cn.com",
              "count": 0
            },
            {
              "value": "*.googletagservices-cn.com",
              "count": 0
            },
            {
              "value": "googletagmanager-cn.com",
              "count": 0
            },
            {
              "value": "*.googletagmanager-cn.com",
              "count": 0
            },
            {
              "value": "googlesyndication-cn.com",
              "count": 0
            },
            {
              "value": "*.googlesyndication-cn.com",
              "count": 0
            },
            {
              "value": "*.safeframe.googlesyndication-cn.com",
              "count": 0
            },
            {
              "value": "app-measurement-cn.com",
              "count": 0
            },
            {
              "value": "*.app-measurement-cn.com",
              "count": 0
            },
            {
              "value": "gvt1-cn.com",
              "count": 0
            },
            {
              "value": "*.gvt1-cn.com",
              "count": 0
            },
            {
              "value": "gvt2-cn.com",
              "count": 0
            },
            {
              "value": "*.gvt2-cn.com",
              "count": 0
            },
            {
              "value": "2mdn-cn.net",
              "count": 0
            },
            {
              "value": "*.2mdn-cn.net",
              "count": 0
            },
            {
              "value": "googleflights-cn.net",
              "count": 0
            },
            {
              "value": "*.googleflights-cn.net",
              "count": 0
            },
            {
              "value": "admob-cn.com",
              "count": 0
            },
            {
              "value": "*.admob-cn.com",
              "count": 0
            },
            {
              "value": "*.gemini.cloud.google.com",
              "count": 0
            },
            {
              "value": "googlesandbox-cn.com",
              "count": 0
            },
            {
              "value": "*.googlesandbox-cn.com",
              "count": 0
            },
            {
              "value": "*.safenup.googlesandbox-cn.com",
              "count": 0
            },
            {
              "value": "*.gstatic.com",
              "count": 0
            },
            {
              "value": "*.metric.gstatic.com",
              "count": 0
            },
            {
              "value": "*.gvt1.com",
              "count": 0
            },
            {
              "value": "*.gcpcdn.gvt1.com",
              "count": 0
            },
            {
              "value": "*.gvt2.com",
              "count": 0
            },
            {
              "value": "*.gcp.gvt2.com",
              "count": 0
            },
            {
              "value": "*.url.google.com",
              "count": 0
            },
            {
              "value": "*.youtube-nocookie.com",
              "count": 0
            },
            {
              "value": "*.ytimg.com",
              "count": 0
            },
            {
              "value": "ai.android",
              "count": 0
            },
            {
              "value": "android.com",
              "count": 0
            },
            {
              "value": "*.android.com",
              "count": 0
            },
            {
              "value": "*.flash.android.com",
              "count": 0
            },
            {
              "value": "g.cn",
              "count": 0
            },
            {
              "value": "*.g.cn",
              "count": 0
            },
            {
              "value": "g.co",
              "count": 0
            },
            {
              "value": "*.g.co",
              "count": 0
            },
            {
              "value": "goo.gl",
              "count": 0
            },
            {
              "value": "www.goo.gl",
              "count": 0
            },
            {
              "value": "google-analytics.com",
              "count": 0
            },
            {
              "value": "*.google-analytics.com",
              "count": 0
            },
            {
              "value": "*.google.com",
              "count": 0
            },
            {
              "value": "googlecommerce.com",
              "count": 0
            },
            {
              "value": "*.googlecommerce.com",
              "count": 0
            },
            {
              "value": "ggpht.cn",
              "count": 0
            },
            {
              "value": "*.ggpht.cn",
              "count": 0
            },
            {
              "value": "urchin.com",
              "count": 0
            },
            {
              "value": "*.urchin.com",
              "count": 0
            },
            {
              "value": "youtu.be",
              "count": 0
            },
            {
              "value": "youtube.com",
              "count": 0
            },
            {
              "value": "*.youtube.com",
              "count": 0
            },
            {
              "value": "music.youtube.com",
              "count": 0
            },
            {
              "value": "*.music.youtube.com",
              "count": 0
            },
            {
              "value": "youtubeeducation.com",
              "count": 0
            },
            {
              "value": "*.youtubeeducation.com",
              "count": 0
            },
            {
              "value": "youtubekids.com",
              "count": 0
            },
            {
              "value": "*.youtubekids.com",
              "count": 0
            },
            {
              "value": "yt.be",
              "count": 0
            },
            {
              "value": "*.yt.be",
              "count": 0
            },
            {
              "value": "android.clients.google.com",
              "count": 0
            },
            {
              "value": "*.android.google.cn",
              "count": 0
            },
            {
              "value": "*.chrome.google.cn",
              "count": 0
            },
            {
              "value": "*.developers.google.cn",
              "count": 0
            },
            {
              "value": "*.aistudio.google.com",
              "count": 0
            },
            {
              "value": "google.ac",
              "count": 0
            },
            {
              "value": "*.google.ac",
              "count": 0
            },
            {
              "value": "google.ad",
              "count": 0
            },
            {
              "value": "*.google.ad",
              "count": 0
            },
            {
              "value": "google.ae",
              "count": 0
            },
            {
              "value": "*.google.ae",
              "count": 0
            },
            {
              "value": "google.af",
              "count": 0
            },
            {
              "value": "*.google.af",
              "count": 0
            },
            {
              "value": "google.ag",
              "count": 0
            },
            {
              "value": "*.google.ag",
              "count": 0
            },
            {
              "value": "google.ai",
              "count": 0
            },
            {
              "value": "*.google.ai",
              "count": 0
            },
            {
              "value": "google.al",
              "count": 0
            },
            {
              "value": "*.google.al",
              "count": 0
            },
            {
              "value": "google.am",
              "count": 0
            },
            {
              "value": "*.google.am",
              "count": 0
            },
            {
              "value": "google.as",
              "count": 0
            },
            {
              "value": "*.google.as",
              "count": 0
            },
            {
              "value": "google.at",
              "count": 0
            },
            {
              "value": "*.google.at",
              "count": 0
            },
            {
              "value": "google.az",
              "count": 0
            },
            {
              "value": "*.google.az",
              "count": 0
            },
            {
              "value": "google.ba",
              "count": 0
            },
            {
              "value": "*.google.ba",
              "count": 0
            },
            {
              "value": "google.be",
              "count": 0
            },
            {
              "value": "*.google.be",
              "count": 0
            },
            {
              "value": "google.bf",
              "count": 0
            },
            {
              "value": "*.google.bf",
              "count": 0
            },
            {
              "value": "google.bg",
              "count": 0
            },
            {
              "value": "*.google.bg",
              "count": 0
            },
            {
              "value": "google.bi",
              "count": 0
            },
            {
              "value": "*.google.bi",
              "count": 0
            },
            {
              "value": "google.bj",
              "count": 0
            },
            {
              "value": "*.google.bj",
              "count": 0
            },
            {
              "value": "google.bs",
              "count": 0
            },
            {
              "value": "*.google.bs",
              "count": 0
            },
            {
              "value": "google.bt",
              "count": 0
            },
            {
              "value": "*.google.bt",
              "count": 0
            },
            {
              "value": "google.by",
              "count": 0
            },
            {
              "value": "*.google.by",
              "count": 0
            },
            {
              "value": "google.bzh",
              "count": 0
            },
            {
              "value": "*.google.bzh",
              "count": 0
            },
            {
              "value": "google.ca",
              "count": 0
            },
            {
              "value": "google.cat",
              "count": 0
            },
            {
              "value": "*.google.cat",
              "count": 0
            },
            {
              "value": "google.cc",
              "count": 0
            },
            {
              "value": "*.google.cc",
              "count": 0
            },
            {
              "value": "google.cd",
              "count": 0
            },
            {
              "value": "*.google.cd",
              "count": 0
            },
            {
              "value": "google.cf",
              "count": 0
            },
            {
              "value": "*.google.cf",
              "count": 0
            },
            {
              "value": "google.cg",
              "count": 0
            },
            {
              "value": "*.google.cg",
              "count": 0
            },
            {
              "value": "google.ch",
              "count": 0
            },
            {
              "value": "*.google.ch",
              "count": 0
            },
            {
              "value": "google.ci",
              "count": 0
            },
            {
              "value": "*.google.ci",
              "count": 0
            },
            {
              "value": "google.cl",
              "count": 0
            },
            {
              "value": "google.cm",
              "count": 0
            },
            {
              "value": "*.google.cm",
              "count": 0
            },
            {
              "value": "google.cn",
              "count": 0
            },
            {
              "value": "*.google.cn",
              "count": 0
            },
            {
              "value": "google.co.ao",
              "count": 0
            },
            {
              "value": "*.google.co.ao",
              "count": 0
            },
            {
              "value": "google.co.bw",
              "count": 0
            },
            {
              "value": "*.google.co.bw",
              "count": 0
            },
            {
              "value": "google.co.ck",
              "count": 0
            },
            {
              "value": "*.google.co.ck",
              "count": 0
            },
            {
              "value": "google.co.cr",
              "count": 0
            },
            {
              "value": "*.google.co.cr",
              "count": 0
            },
            {
              "value": "google.co.hu",
              "count": 0
            },
            {
              "value": "*.google.co.hu",
              "count": 0
            },
            {
              "value": "google.co.id",
              "count": 0
            },
            {
              "value": "*.google.co.id",
              "count": 0
            },
            {
              "value": "google.co.il",
              "count": 0
            },
            {
              "value": "*.google.co.il",
              "count": 0
            },
            {
              "value": "google.co.im",
              "count": 0
            },
            {
              "value": "*.google.co.im",
              "count": 0
            },
            {
              "value": "google.co.in",
              "count": 0
            },
            {
              "value": "google.co.je",
              "count": 0
            },
            {
              "value": "*.google.co.je",
              "count": 0
            },
            {
              "value": "google.co.jp",
              "count": 0
            },
            {
              "value": "google.co.ke",
              "count": 0
            },
            {
              "value": "*.google.co.ke",
              "count": 0
            },
            {
              "value": "google.co.kr",
              "count": 0
            },
            {
              "value": "*.google.co.kr",
              "count": 0
            },
            {
              "value": "google.co.ls",
              "count": 0
            },
            {
              "value": "*.google.co.ls",
              "count": 0
            },
            {
              "value": "google.co.ma",
              "count": 0
            },
            {
              "value": "*.google.co.ma",
              "count": 0
            },
            {
              "value": "google.co.mz",
              "count": 0
            },
            {
              "value": "*.google.co.mz",
              "count": 0
            },
            {
              "value": "google.co.nz",
              "count": 0
            },
            {
              "value": "*.google.co.nz",
              "count": 0
            },
            {
              "value": "google.co.th",
              "count": 0
            },
            {
              "value": "*.google.co.th",
              "count": 0
            },
            {
              "value": "google.co.tz",
              "count": 0
            },
            {
              "value": "*.google.co.tz",
              "count": 0
            },
            {
              "value": "google.co.ug",
              "count": 0
            },
            {
              "value": "*.google.co.ug",
              "count": 0
            },
            {
              "value": "google.co.uk",
              "count": 0
            },
            {
              "value": "google.co.uz",
              "count": 0
            },
            {
              "value": "*.google.co.uz",
              "count": 0
            },
            {
              "value": "google.co.ve",
              "count": 0
            },
            {
              "value": "*.google.co.ve",
              "count": 0
            },
            {
              "value": "google.co.vi",
              "count": 0
            },
            {
              "value": "*.google.co.vi",
              "count": 0
            },
            {
              "value": "google.co.za",
              "count": 0
            },
            {
              "value": "*.google.co.za",
              "count": 0
            },
            {
              "value": "google.co.zm",
              "count": 0
            },
            {
              "value": "*.google.co.zm",
              "count": 0
            },
            {
              "value": "google.co.zw",
              "count": 0
            },
            {
              "value": "*.google.co.zw",
              "count": 0
            },
            {
              "value": "google.com.af",
              "count": 0
            },
            {
              "value": "*.google.com.af",
              "count": 0
            },
            {
              "value": "google.com.ag",
              "count": 0
            },
            {
              "value": "*.google.com.ag",
              "count": 0
            },
            {
              "value": "google.com.ai",
              "count": 0
            },
            {
              "value": "*.google.com.ai",
              "count": 0
            },
            {
              "value": "google.com.ar",
              "count": 0
            },
            {
              "value": "google.com.au",
              "count": 0
            },
            {
              "value": "google.com.bd",
              "count": 0
            },
            {
              "value": "*.google.com.bd",
              "count": 0
            },
            {
              "value": "google.com.bh",
              "count": 0
            },
            {
              "value": "*.google.com.bh",
              "count": 0
            },
            {
              "value": "google.com.bn",
              "count": 0
            },
            {
              "value": "*.google.com.bn",
              "count": 0
            },
            {
              "value": "google.com.bo",
              "count": 0
            },
            {
              "value": "*.google.com.bo",
              "count": 0
            },
            {
              "value": "google.com.br",
              "count": 0
            },
            {
              "value": "google.com.by",
              "count": 0
            },
            {
              "value": "*.google.com.by",
              "count": 0
            },
            {
              "value": "google.com.bz",
              "count": 0
            },
            {
              "value": "*.google.com.bz",
              "count": 0
            },
            {
              "value": "google.com.co",
              "count": 0
            },
            {
              "value": "google.com.cu",
              "count": 0
            },
            {
              "value": "*.google.com.cu",
              "count": 0
            },
            {
              "value": "google.com.cy",
              "count": 0
            },
            {
              "value": "*.google.com.cy",
              "count": 0
            },
            {
              "value": "google.com.do",
              "count": 0
            },
            {
              "value": "*.google.com.do",
              "count": 0
            },
            {
              "value": "google.com.ec",
              "count": 0
            },
            {
              "value": "*.google.com.ec",
              "count": 0
            },
            {
              "value": "google.com.eg",
              "count": 0
            },
            {
              "value": "*.google.com.eg",
              "count": 0
            },
            {
              "value": "google.com.et",
              "count": 0
            },
            {
              "value": "*.google.com.et",
              "count": 0
            },
            {
              "value": "google.com.fj",
              "count": 0
            },
            {
              "value": "*.google.com.fj",
              "count": 0
            },
            {
              "value": "google.com.ge",
              "count": 0
            },
            {
              "value": "*.google.com.ge",
              "count": 0
            },
            {
              "value": "google.com.gh",
              "count": 0
            },
            {
              "value": "*.google.com.gh",
              "count": 0
            },
            {
              "value": "google.com.gi",
              "count": 0
            },
            {
              "value": "*.google.com.gi",
              "count": 0
            },
            {
              "value": "google.com.gr",
              "count": 0
            },
            {
              "value": "*.google.com.gr",
              "count": 0
            },
            {
              "value": "google.com.gt",
              "count": 0
            },
            {
              "value": "*.google.com.gt",
              "count": 0
            },
            {
              "value": "google.com.hk",
              "count": 0
            },
            {
              "value": "*.google.com.hk",
              "count": 0
            },
            {
              "value": "google.com.iq",
              "count": 0
            },
            {
              "value": "*.google.com.iq",
              "count": 0
            },
            {
              "value": "google.com.jm",
              "count": 0
            },
            {
              "value": "*.google.com.jm",
              "count": 0
            },
            {
              "value": "google.com.jo",
              "count": 0
            },
            {
              "value": "*.google.com.jo",
              "count": 0
            },
            {
              "value": "google.com.kh",
              "count": 0
            },
            {
              "value": "*.google.com.kh",
              "count": 0
            },
            {
              "value": "google.com.kw",
              "count": 0
            },
            {
              "value": "*.google.com.kw",
              "count": 0
            },
            {
              "value": "google.com.lb",
              "count": 0
            },
            {
              "value": "*.google.com.lb",
              "count": 0
            },
            {
              "value": "google.com.ly",
              "count": 0
            },
            {
              "value": "*.google.com.ly",
              "count": 0
            },
            {
              "value": "google.com.mm",
              "count": 0
            },
            {
              "value": "*.google.com.mm",
              "count": 0
            },
            {
              "value": "google.com.mt",
              "count": 0
            },
            {
              "value": "*.google.com.mt",
              "count": 0
            },
            {
              "value": "google.com.mx",
              "count": 0
            },
            {
              "value": "google.com.my",
              "count": 0
            },
            {
              "value": "*.google.com.my",
              "count": 0
            },
            {
              "value": "google.com.na",
              "count": 0
            },
            {
              "value": "*.google.com.na",
              "count": 0
            },
            {
              "value": "google.com.nf",
              "count": 0
            },
            {
              "value": "*.google.com.nf",
              "count": 0
            },
            {
              "value": "google.com.ng",
              "count": 0
            },
            {
              "value": "*.google.com.ng",
              "count": 0
            },
            {
              "value": "google.com.ni",
              "count": 0
            },
            {
              "value": "*.google.com.ni",
              "count": 0
            },
            {
              "value": "google.com.np",
              "count": 0
            },
            {
              "value": "*.google.com.np",
              "count": 0
            },
            {
              "value": "google.com.nr",
              "count": 0
            },
            {
              "value": "*.google.com.nr",
              "count": 0
            },
            {
              "value": "google.com.om",
              "count": 0
            },
            {
              "value": "*.google.com.om",
              "count": 0
            },
            {
              "value": "google.com.pa",
              "count": 0
            },
            {
              "value": "*.google.com.pa",
              "count": 0
            },
            {
              "value": "google.com.pe",
              "count": 0
            },
            {
              "value": "*.google.com.pe",
              "count": 0
            },
            {
              "value": "google.com.pg",
              "count": 0
            },
            {
              "value": "*.google.com.pg",
              "count": 0
            },
            {
              "value": "google.com.ph",
              "count": 0
            },
            {
              "value": "*.google.com.ph",
              "count": 0
            },
            {
              "value": "google.com.pk",
              "count": 0
            },
            {
              "value": "*.google.com.pk",
              "count": 0
            },
            {
              "value": "google.com.pl",
              "count": 0
            },
            {
              "value": "*.google.com.pl",
              "count": 0
            },
            {
              "value": "google.com.pr",
              "count": 0
            },
            {
              "value": "*.google.com.pr",
              "count": 0
            },
            {
              "value": "google.com.py",
              "count": 0
            },
            {
              "value": "*.google.com.py",
              "count": 0
            },
            {
              "value": "google.com.qa",
              "count": 0
            },
            {
              "value": "*.google.com.qa",
              "count": 0
            },
            {
              "value": "google.com.ru",
              "count": 0
            },
            {
              "value": "*.google.com.ru",
              "count": 0
            },
            {
              "value": "google.com.sa",
              "count": 0
            },
            {
              "value": "*.google.com.sa",
              "count": 0
            },
            {
              "value": "google.com.sb",
              "count": 0
            },
            {
              "value": "*.google.com.sb",
              "count": 0
            },
            {
              "value": "google.com.sg",
              "count": 0
            },
            {
              "value": "*.google.com.sg",
              "count": 0
            },
            {
              "value": "google.com.sl",
              "count": 0
            },
            {
              "value": "*.google.com.sl",
              "count": 0
            },
            {
              "value": "google.com.sv",
              "count": 0
            },
            {
              "value": "*.google.com.sv",
              "count": 0
            },
            {
              "value": "google.com.tj",
              "count": 0
            },
            {
              "value": "*.google.com.tj",
              "count": 0
            },
            {
              "value": "google.com.tn",
              "count": 0
            },
            {
              "value": "*.google.com.tn",
              "count": 0
            },
            {
              "value": "google.com.tr",
              "count": 0
            },
            {
              "value": "google.com.tw",
              "count": 0
            },
            {
              "value": "*.google.com.tw",
              "count": 0
            },
            {
              "value": "google.com.ua",
              "count": 0
            },
            {
              "value": "*.google.com.ua",
              "count": 0
            },
            {
              "value": "google.com.uy",
              "count": 0
            },
            {
              "value": "*.google.com.uy",
              "count": 0
            },
            {
              "value": "google.com.vc",
              "count": 0
            },
            {
              "value": "*.google.com.vc",
              "count": 0
            },
            {
              "value": "google.com.ve",
              "count": 0
            },
            {
              "value": "*.google.com.ve",
              "count": 0
            },
            {
              "value": "google.com.vn",
              "count": 0
            },
            {
              "value": "google.cv",
              "count": 0
            },
            {
              "value": "*.google.cv",
              "count": 0
            },
            {
              "value": "google.cz",
              "count": 0
            },
            {
              "value": "*.google.cz",
              "count": 0
            },
            {
              "value": "google.de",
              "count": 0
            },
            {
              "value": "google.dj",
              "count": 0
            },
            {
              "value": "*.google.dj",
              "count": 0
            },
            {
              "value": "google.dk",
              "count": 0
            },
            {
              "value": "*.google.dk",
              "count": 0
            },
            {
              "value": "google.dm",
              "count": 0
            },
            {
              "value": "*.google.dm",
              "count": 0
            },
            {
              "value": "google.dz",
              "count": 0
            },
            {
              "value": "*.google.dz",
              "count": 0
            },
            {
              "value": "google.ee",
              "count": 0
            },
            {
              "value": "*.google.ee",
              "count": 0
            },
            {
              "value": "google.es",
              "count": 0
            },
            {
              "value": "google.eus",
              "count": 0
            },
            {
              "value": "*.google.eus",
              "count": 0
            },
            {
              "value": "google.fi",
              "count": 0
            },
            {
              "value": "*.google.fi",
              "count": 0
            },
            {
              "value": "google.fm",
              "count": 0
            },
            {
              "value": "*.google.fm",
              "count": 0
            },
            {
              "value": "google.fr",
              "count": 0
            },
            {
              "value": "google.frl",
              "count": 0
            },
            {
              "value": "*.google.frl",
              "count": 0
            },
            {
              "value": "google.ga",
              "count": 0
            },
            {
              "value": "*.google.ga",
              "count": 0
            },
            {
              "value": "google.gal",
              "count": 0
            },
            {
              "value": "*.google.gal",
              "count": 0
            },
            {
              "value": "google.ge",
              "count": 0
            },
            {
              "value": "*.google.ge",
              "count": 0
            },
            {
              "value": "google.gg",
              "count": 0
            },
            {
              "value": "*.google.gg",
              "count": 0
            },
            {
              "value": "google.gl",
              "count": 0
            },
            {
              "value": "*.google.gl",
              "count": 0
            },
            {
              "value": "google.gm",
              "count": 0
            },
            {
              "value": "*.google.gm",
              "count": 0
            },
            {
              "value": "google.gp",
              "count": 0
            },
            {
              "value": "*.google.gp",
              "count": 0
            },
            {
              "value": "google.gr",
              "count": 0
            },
            {
              "value": "*.google.gr",
              "count": 0
            },
            {
              "value": "google.gy",
              "count": 0
            },
            {
              "value": "*.google.gy",
              "count": 0
            },
            {
              "value": "google.hk",
              "count": 0
            },
            {
              "value": "*.google.hk",
              "count": 0
            },
            {
              "value": "google.hn",
              "count": 0
            },
            {
              "value": "*.google.hn",
              "count": 0
            },
            {
              "value": "google.hr",
              "count": 0
            },
            {
              "value": "*.google.hr",
              "count": 0
            },
            {
              "value": "google.ht",
              "count": 0
            },
            {
              "value": "*.google.ht",
              "count": 0
            },
            {
              "value": "google.hu",
              "count": 0
            },
            {
              "value": "google.ie",
              "count": 0
            },
            {
              "value": "*.google.ie",
              "count": 0
            },
            {
              "value": "google.im",
              "count": 0
            },
            {
              "value": "*.google.im",
              "count": 0
            },
            {
              "value": "google.in",
              "count": 0
            },
            {
              "value": "*.google.in",
              "count": 0
            },
            {
              "value": "google.info",
              "count": 0
            },
            {
              "value": "*.google.info",
              "count": 0
            },
            {
              "value": "google.iq",
              "count": 0
            },
            {
              "value": "*.google.iq",
              "count": 0
            },
            {
              "value": "google.ir",
              "count": 0
            },
            {
              "value": "*.google.ir",
              "count": 0
            },
            {
              "value": "google.is",
              "count": 0
            },
            {
              "value": "*.google.is",
              "count": 0
            },
            {
              "value": "google.it",
              "count": 0
            },
            {
              "value": "google.it.ao",
              "count": 0
            },
            {
              "value": "*.google.it.ao",
              "count": 0
            },
            {
              "value": "google.je",
              "count": 0
            },
            {
              "value": "*.google.je",
              "count": 0
            },
            {
              "value": "google.jo",
              "count": 0
            },
            {
              "value": "*.google.jo",
              "count": 0
            },
            {
              "value": "google.jobs",
              "count": 0
            },
            {
              "value": "*.google.jobs",
              "count": 0
            },
            {
              "value": "google.jp",
              "count": 0
            },
            {
              "value": "*.google.jp",
              "count": 0
            },
            {
              "value": "google.kg",
              "count": 0
            },
            {
              "value": "*.google.kg",
              "count": 0
            },
            {
              "value": "google.ki",
              "count": 0
            },
            {
              "value": "*.google.ki",
              "count": 0
            },
            {
              "value": "google.kz",
              "count": 0
            },
            {
              "value": "*.google.kz",
              "count": 0
            },
            {
              "value": "google.la",
              "count": 0
            },
            {
              "value": "*.google.la",
              "count": 0
            },
            {
              "value": "google.li",
              "count": 0
            },
            {
              "value": "*.google.li",
              "count": 0
            },
            {
              "value": "google.lk",
              "count": 0
            },
            {
              "value": "*.google.lk",
              "count": 0
            },
            {
              "value": "google.lt",
              "count": 0
            },
            {
              "value": "*.google.lt",
              "count": 0
            },
            {
              "value": "google.lu",
              "count": 0
            },
            {
              "value": "*.google.lu",
              "count": 0
            },
            {
              "value": "google.lv",
              "count": 0
            },
            {
              "value": "*.google.lv",
              "count": 0
            },
            {
              "value": "google.md",
              "count": 0
            },
            {
              "value": "*.google.md",
              "count": 0
            },
            {
              "value": "google.me",
              "count": 0
            },
            {
              "value": "*.google.me",
              "count": 0
            },
            {
              "value": "google.mg",
              "count": 0
            },
            {
              "value": "*.google.mg",
              "count": 0
            },
            {
              "value": "google.mk",
              "count": 0
            },
            {
              "value": "*.google.mk",
              "count": 0
            },
            {
              "value": "google.ml",
              "count": 0
            },
            {
              "value": "*.google.ml",
              "count": 0
            },
            {
              "value": "google.mn",
              "count": 0
            },
            {
              "value": "*.google.mn",
              "count": 0
            },
            {
              "value": "google.ms",
              "count": 0
            },
            {
              "value": "*.google.ms",
              "count": 0
            },
            {
              "value": "google.mu",
              "count": 0
            },
            {
              "value": "*.google.mu",
              "count": 0
            },
            {
              "value": "google.mv",
              "count": 0
            },
            {
              "value": "*.google.mv",
              "count": 0
            },
            {
              "value": "google.mw",
              "count": 0
            },
            {
              "value": "*.google.mw",
              "count": 0
            },
            {
              "value": "google.ne",
              "count": 0
            },
            {
              "value": "*.google.ne",
              "count": 0
            },
            {
              "value": "google.ne.jp",
              "count": 0
            },
            {
              "value": "*.google.ne.jp",
              "count": 0
            },
            {
              "value": "google.net",
              "count": 0
            },
            {
              "value": "*.google.net",
              "count": 0
            },
            {
              "value": "google.ng",
              "count": 0
            },
            {
              "value": "*.google.ng",
              "count": 0
            },
            {
              "value": "google.nl",
              "count": 0
            },
            {
              "value": "google.no",
              "count": 0
            },
            {
              "value": "*.google.no",
              "count": 0
            },
            {
              "value": "google.nr",
              "count": 0
            },
            {
              "value": "*.google.nr",
              "count": 0
            },
            {
              "value": "google.nu",
              "count": 0
            },
            {
              "value": "*.google.nu",
              "count": 0
            },
            {
              "value": "google.off.ai",
              "count": 0
            },
            {
              "value": "*.google.off.ai",
              "count": 0
            },
            {
              "value": "google.pk",
              "count": 0
            },
            {
              "value": "*.google.pk",
              "count": 0
            },
            {
              "value": "google.pl",
              "count": 0
            },
            {
              "value": "google.pn",
              "count": 0
            },
            {
              "value": "*.google.pn",
              "count": 0
            },
            {
              "value": "google.ps",
              "count": 0
            },
            {
              "value": "*.google.ps",
              "count": 0
            },
            {
              "value": "google.pt",
              "count": 0
            },
            {
              "value": "google.ro",
              "count": 0
            },
            {
              "value": "*.google.ro",
              "count": 0
            },
            {
              "value": "google.rs",
              "count": 0
            },
            {
              "value": "*.google.rs",
              "count": 0
            },
            {
              "value": "google.ru",
              "count": 0
            },
            {
              "value": "*.google.ru",
              "count": 0
            },
            {
              "value": "google.rw",
              "count": 0
            },
            {
              "value": "*.google.rw",
              "count": 0
            },
            {
              "value": "google.sc",
              "count": 0
            },
            {
              "value": "*.google.sc",
              "count": 0
            },
            {
              "value": "google.se",
              "count": 0
            },
            {
              "value": "*.google.se",
              "count": 0
            },
            {
              "value": "google.sh",
              "count": 0
            },
            {
              "value": "*.google.sh",
              "count": 0
            },
            {
              "value": "google.si",
              "count": 0
            },
            {
              "value": "*.google.si",
              "count": 0
            },
            {
              "value": "google.sk",
              "count": 0
            },
            {
              "value": "*.google.sk",
              "count": 0
            },
            {
              "value": "google.sm",
              "count": 0
            },
            {
              "value": "*.google.sm",
              "count": 0
            },
            {
              "value": "google.sn",
              "count": 0
            },
            {
              "value": "*.google.sn",
              "count": 0
            },
            {
              "value": "google.so",
              "count": 0
            },
            {
              "value": "*.google.so",
              "count": 0
            },
            {
              "value": "google.sr",
              "count": 0
            },
            {
              "value": "*.google.sr",
              "count": 0
            },
            {
              "value": "google.st",
              "count": 0
            },
            {
              "value": "*.google.st",
              "count": 0
            },
            {
              "value": "google.td",
              "count": 0
            },
            {
              "value": "*.google.td",
              "count": 0
            },
            {
              "value": "google.tel",
              "count": 0
            },
            {
              "value": "*.google.tel",
              "count": 0
            },
            {
              "value": "google.tg",
              "count": 0
            },
            {
              "value": "*.google.tg",
              "count": 0
            },
            {
              "value": "google.tk",
              "count": 0
            },
            {
              "value": "*.google.tk",
              "count": 0
            },
            {
              "value": "google.tl",
              "count": 0
            },
            {
              "value": "*.google.tl",
              "count": 0
            },
            {
              "value": "google.tm",
              "count": 0
            },
            {
              "value": "*.google.tm",
              "count": 0
            },
            {
              "value": "google.tn",
              "count": 0
            },
            {
              "value": "*.google.tn",
              "count": 0
            },
            {
              "value": "google.to",
              "count": 0
            },
            {
              "value": "*.google.to",
              "count": 0
            },
            {
              "value": "google.tt",
              "count": 0
            },
            {
              "value": "*.google.tt",
              "count": 0
            },
            {
              "value": "google.us",
              "count": 0
            },
            {
              "value": "*.google.us",
              "count": 0
            },
            {
              "value": "google.uz",
              "count": 0
            },
            {
              "value": "*.google.uz",
              "count": 0
            },
            {
              "value": "google.vg",
              "count": 0
            },
            {
              "value": "*.google.vg",
              "count": 0
            },
            {
              "value": "google.vu",
              "count": 0
            },
            {
              "value": "*.google.vu",
              "count": 0
            },
            {
              "value": "google.ws",
              "count": 0
            },
            {
              "value": "*.google.ws",
              "count": 0
            },
            {
              "value": "gstatic.com",
              "count": 0
            },
            {
              "value": "*.2mdn.net",
              "count": 0
            },
            {
              "value": "*.au.doubleclick.net",
              "count": 0
            },
            {
              "value": "*.cc-dt.com",
              "count": 0
            },
            {
              "value": "*.de.doubleclick.net",
              "count": 0
            },
            {
              "value": "doubleclick.com",
              "count": 0
            },
            {
              "value": "*.doubleclick.com",
              "count": 0
            },
            {
              "value": "*.fls.doubleclick.net",
              "count": 0
            },
            {
              "value": "*.fr.doubleclick.net",
              "count": 0
            },
            {
              "value": "*.jp.doubleclick.net",
              "count": 0
            },
            {
              "value": "*.uk.doubleclick.net",
              "count": 0
            },
            {
              "value": "ad.mo.doubleclick.net",
              "count": 0
            },
            {
              "value": "doubleclick.net",
              "count": 0
            },
            {
              "value": "*.doubleclick.net",
              "count": 0
            },
            {
              "value": "*.googleadsserving.cn",
              "count": 0
            },
            {
              "value": "google.ua",
              "count": 0
            },
            {
              "value": "*.google.ua",
              "count": 0
            }
          ],
          "sources": {
            "passive": 1759987480923
          },
          "common_name": {
            "value": "google.com",
            "count": 351
          },
          "issuer_common_name": {
            "value": "WR2",
            "count": 2028
          },
          "not_after": {
            "value": 20251215,
            "count": 3394692
          },
          "not_before": {
            "value": 20250922,
            "count": 4101668
          },
          "duration": {
            "value": 84,
            "count": 1024089
          }
        }
      ],
      "tld": "com",
      "website_response": 200,
      "data_updated_timestamp": "2025-10-10T14:05:43.105000",
      "website_title": {
        "value": "Google",
        "count": 284319
      },
      "server_type": {
        "value": "Playlog",
        "count": 351551
      },
      "first_seen": {
        "value": "2001-05-03T00:00:00Z",
        "count": 0
      },
      "tags": []
    }
  ]
}


def test_get_domain_reputation_action_success():
    action = DomaintoolsDomainReputation()
    action.module.configuration = {
        "host": "https://api.domaintools.com/",
        "api_key": "LOREM",
        "api_username": "IPSUM",
    }

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(url="https://api.domaintools.com/v1/iris-investigate/", status_code=200, json=DT_OUTPUT)

        result = action.run({"sekoia_base_url": SEKOIA_BASE_URL, "alert": ALERT})
        assert result is not None
        assert result["title"] == ALERT["title"]


def test_create_alert_action_api_error(requests_mock):
    mock_alert = requests_mock.post(url="https://api.domaintools.com/v1/iris-investigate/", status_code=500)

    action = TheHiveCreateAlertV5()
    action.module.configuration = {
        "base_url": "https://api.domaintools.com/",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    result = action.run({"sekoia_base_url": SEKOIA_BASE_URL, "alert": ALERT})

    assert not result
    assert mock_alert.call_count == 1
