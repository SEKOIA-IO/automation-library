# README

## **Key Features**

### 1. **Security Enhancements**
- API key loaded from environment variable (`VT_API_KEY`)
- Validation to prevent running with hardcoded keys
- Proper file existence checks before scanning

### 2. **Error Handling**
- Try-catch blocks for all API calls
- Specific exception handling for `vt.APIError`, `FileNotFoundError`, `IOError`
- Detailed error logging and tracking
- Graceful degradation when tests fail

### 3. **Official vt-py Library Usage**
- `client.scan_url()` for URL scanning
- `client.scan_file()` for file scanning
- `client.get_object()` for retrieving reports
- `client.get_json()` for raw JSON responses
- `client.iterator()` for paginated results
- Proper context manager usage (`with vt.Client()`)

### 4. **Structured Results**
- `TestResult` dataclass for type-safe result storage
- JSON output with detailed success/error information
- Summary statistics at the end

### 5. **Comprehensive Coverage**
All your required actions are covered:
- ✅ Scan File
- ✅ Get IOC Report (IP, URL, domain, file)
- ✅ Get Comments
- ✅ Get Vulnerability Associations
- ✅ Get File Sandbox Report
- ✅ Scan URL
- ✅ Get Passive DNS Data
- ✅ Get Vulnerability Report

## **Usage**

```bash
# Install vt-py
pip install vt-py

# Set your API key
export VT_API_KEY='your_actual_api_key'

# Run the script
python script.py

# Optional: test with a file
# Modify main() to include: tester.run_all_tests(test_file_path="your_file.png")
```

The script will generate `vt_test_results.json` with detailed results and print a summary to the console.