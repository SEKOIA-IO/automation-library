# 🚀 Quick Start Guide

Quick start guide for local Docker development of Sekoia automation modules.

## 📦 Setup in 3 Steps

### 1️⃣ Setup a Module

```bash
cd automation-library
bash .docker/setup-module.sh ./HTTP
```

### 2️⃣ Edit Configuration

```bash
cd HTTP

# Module configuration (API keys, etc.)
nano config/module_configuration.json

# Action configuration (files are pre-filled with examples)
nano config/request_args.json
```

Example for HTTP request:
```json
{
  "url": "https://api.github.com/repos/SEKOIA-IO/sekoia-automation-sdk",
  "method": "GET",
  "verify_ssl": true
}
```

### 3️⃣ Build and Run

```bash
# Build the image
make build

# Run an action
make run ACTION=request

# View results
cat results/action_results.json | jq .
```

## 🎯 Essential Commands

### With Make (from module directory)

```bash
cd HTTP

# Display help
make help

# List available actions
make list-actions

# Build
make build

# Run an action
make run ACTION=request

# Open shell for debugging
make shell

# Check configuration
make check-config

# Clean results
make clean

# Clean everything
make clean-all
```

## 🔍 Complete Workflow

### Example: HTTP Module

```bash
# 1. Setup
bash .docker/setup-module.sh ./HTTP
cd HTTP

# 2. Config (files are already pre-filled)
cat config/request_args.json
# {
#   "url": "https://example.com/api/endpoint",
#   "method": "GET",
#   "verify_ssl": true
# }

# Edit with your actual values
nano config/request_args.json

# 3. Build
make build

# 4. Run
make run ACTION=request

# 5. View results
cat results/action_results.json | jq .

# 6. Debug if needed
make shell
# > python main.py request
```

### Example: TheHiveV5 Module

```bash
# 1. Setup
bash .docker/setup-module.sh ./TheHiveV5
cd TheHiveV5

# 2. Module configuration
cat > config/module_configuration.json << 'EOF'
{
  "base_url": "https://thehive.example.com",
  "apikey": "your-api-key-here",
  "organisation": "your-org"
}
EOF

# 3. Action configuration
cat > config/thehive_create_alert_args.json << 'EOF'
{
  "alert": {
    "title": "Test Alert from Docker",
    "type": "test",
    "source": "automation",
    "description": "Test automation"
  }
}
EOF

# 4. Build & Run
make build
make run ACTION=thehive_create_alert

# 5. Results
cat results/action_results.json | jq .
```

## ✨ Features

### ✅ Correct Permissions
Files created in `results/` belong to your user (not root)!

```bash
ls -la results/
# -rw-r--r-- youruser yourgroup ... ✅
```

### ✅ Pre-filled Configuration
`config/*_args.json` files are generated with examples based on JSON schemas.

### ✅ Easy Cleanup
```bash
# Clean everything and start over
bash .docker/setup-module.sh --clean ./HTTP
bash .docker/setup-module.sh ./HTTP
```

### ✅ Automatic Result Saving
The patched `main.py` always saves results to `results/action_results.json`, even if the callback fails:

```bash
# Results are always saved locally
make run ACTION=your_action

# View the results
cat results/action_results.json | jq .
```

## 🐛 Troubleshooting

### Permission Issues

```bash
# Check your UID/GID
cat .env | grep USER_ID
# USER_ID=1000
# GROUP_ID=1000

# Rebuild if necessary
make rebuild
```

### Action Not Found

```bash
# List available actions
make list-actions

# Verify config file exists
ls -la config/
```

### Build Error

```bash
# Rebuild without cache
make rebuild

# Check the Dockerfile
cat Dockerfile
```

### "Invalid URL" Error but No Results

```bash
# The patched main.py handles this automatically
make run ACTION=your_action

# Results are saved to results/action_results.json
cat results/action_results.json | jq .
```

## 📚 Further Reading

- **[README.md](README.md)** - Complete documentation
- **[CHANGELOG.md](CHANGELOG.md)** - Version history
- `make help` - Makefile help

## 🎉 That's It!

You're ready to develop and test your modules locally with Docker! 🚀

## 💡 Pro Tips

1. **Use `make run` for local testing** - Results are always saved automatically
2. **Check `results/action_results.json`** - Contains status, results, errors, and logs
3. **Use `make shell`** - Debug interactively inside the container
4. **Configuration is auto-generated** - Just fill in the placeholders
5. **No root permissions needed** - UID/GID mapping handles permissions automatically
