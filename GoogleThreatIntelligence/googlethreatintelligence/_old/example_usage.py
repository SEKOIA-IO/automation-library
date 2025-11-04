from gti_client import GTIClient

#pip3 install vt-py
#export VT_API_KEY="your_api_key_here"

def print_analysis_summary(report: dict, name: str = "Report"):
    """Print a concise summary of last_analysis_stats if available."""
    if not report:
        print(f"[Info] {name}: No data found.")
        return
    attributes = report.get("data", {}).get("attributes", {})
    stats = attributes.get("last_analysis_stats", {})
    if stats:
        print(f"[Summary] {name}: Malicious={stats.get('malicious',0)}, Suspicious={stats.get('suspicious',0)}, Harmless={stats.get('harmless',0)}")
    else:
        print(f"[Info] {name}: Data retrieved, no analysis stats available.")

def main():
    gti = GTIClient()

    try:
        # -----------------------
        # 1. Scan File
        # -----------------------
        file_path = "sample.exe"  # replace with a real file path
        """ file_report = gti.scan_file(file_path)
        print_analysis_summary(file_report, f"File Scan ({file_path})")

        # -----------------------
        # 2. Scan URL
        # -----------------------
        url = "http://www.eicar.org/download/eicar.com"  # public test URL
        url_report = gti.scan_url(url)
        print_analysis_summary(url_report, f"URL Scan ({url})") """

        # -----------------------
        # 3. Get IOC Report
        # -----------------------
        ip = "76jdd2ir2embyv47.onion"
        ip_report = gti.get_ioc_report("ip_addresses", ip)
        print_analysis_summary(ip_report, f"IOC Report (IP {ip})")

        domain = "example.com"
        domain_report = gti.get_ioc_report("domains", domain)
        print_analysis_summary(domain_report, f"IOC Report (Domain {domain})")

        file_hash = "3ecc0186adba60fb53e9f6c494623dcea979a95c3e66a52896693b8d22f5e18b"  # WanaCry sample
        file_hash_report = gti.get_ioc_report("files", file_hash)
        print_analysis_summary(file_hash_report, f"IOC Report (File {file_hash})")

        # -----------------------
        # 4. Get Comments
        # -----------------------
        comments = gti.get_comments("files", file_hash)
        print(f"[Info] Comments for {file_hash}: {len(comments)} found.")

        # -----------------------
        # 5. Get Vulnerability Associations
        # -----------------------
        vulns = gti.get_vulnerabilities("ip_addresses", ip)
        print(f"[Info] Vulnerabilities associated with IP {ip}: {len(vulns)} found.")

        # -----------------------
        # 6. Get File Sandbox Report
        # -----------------------
        if file_hash_report:
            file_behaviour = gti.get_file_behaviour(file_hash)
            print(f"[Info] Sandbox behaviours for {file_hash}: {len(file_behaviour.get('data',{})) if file_behaviour else 0}")

        # -----------------------
        # 7. Get Curated Associations
        # -----------------------
        curated = gti.get_curated("collections", "cti-example-collection")  # replace with valid collection
        print(f"[Info] Curated associations retrieved: {len(curated.get('data',{})) if curated else 0}")

        # -----------------------
        # 8. Get Passive DNS Data
        # -----------------------
        dns_data = gti.get_passive_dns("domains", domain)
        print(f"[Info] Passive DNS resolutions for {domain}: {len(dns_data)} found.")

        # -----------------------
        # 9. Get Vulnerability Report
        # -----------------------
        cve_id = "cve-2024-6284"  # example CVE
        cve_report = gti.get_vulnerability_report(cve_id)
        print(f"[Info] Vulnerability report for {cve_id}: {bool(cve_report)}")

    finally:
        gti.close()

if __name__ == "__main__":
    main()
