# 🐳 Sekoia Automation Module - Local Development Kit

Standardized tools for local development and testing of Sekoia automation modules with Docker.

## 📋 Overview

This standardized solution enables you to:
- ✅ Test module actions locally without deployment
- ✅ Debug easily with detailed logs and result capture
- ✅ Standardize configuration across all modules
- ✅ Simplify the development process

## 🔧 Prerequisites

### Standard Environment

Before using this development kit, ensure you have:

#### Required Software
- **Docker** (version 20.10 or higher)
  - Docker Engine installed and running
  - User added to `docker` group (or sudo access)
  - Test: `docker --version`
- **Docker Compose** (version 1.29 or higher, or Docker Compose v2)
  - Test: `docker-compose --version` or `docker compose version`
- **Make** utility
  - Test: `make --version`
- **Bash** (version 4.0 or higher)
  - Test: `bash --version`
- **Python 3** (for config generation)
  - Test: `python3 --version`
- **jq** (optional, for JSON formatting)
  - Test: `jq --version`

#### System Requirements
- **Disk Space**: Minimum 2 GB free for Docker images
- **RAM**: Minimum 2 GB available
- **Network**: Internet access for initial Docker image pulls (see Network Requirements below)

#### Network Requirements

##### For Standard Environment (Internet-Connected)

**Outbound flows required for initial setup and build:**

| Destination | Protocol/Port | Purpose | Required When |
|-------------|--------------|---------|---------------|
| `registry-1.docker.io` | HTTPS/443 | Docker Hub - Pull base images | Initial build |
| `auth.docker.io` | HTTPS/443 | Docker Hub authentication | Initial build |
| `production.cloudflare.docker.com` | HTTPS/443 | Docker Hub CDN | Initial build |
| `pypi.org` | HTTPS/443 | Python Package Index (pip) | Initial build |
| `files.pythonhosted.org` | HTTPS/443 | PyPI package downloads | Initial build |
| `github.com` | HTTPS/443 | Git repositories (if using git+https in dependencies) | Initial build (optional) |
| `raw.githubusercontent.com` | HTTPS/443 | GitHub raw content | Initial build (optional) |

**DNS resolution required:**
- All hostnames listed above must be resolvable
- Recommend: `8.8.8.8`, `1.1.1.1` or corporate DNS

**Bandwidth estimation:**
- Initial Docker image pull: ~900 MB - 1.5 GB
- Python packages (per module): ~50-200 MB
- **Total for first build**: ~1-2 GB download

##### For Air-Gapped Environment

**NO outbound internet access required** once properly configured.

**Internal network flows (within air-gapped network):**

| Source | Destination | Protocol/Port | Purpose | Required |
|--------|-------------|--------------|---------|----------|
| Developer workstation | Local PyPI mirror | HTTP/8080 (configurable) | Python package downloads | Yes |
| Docker build | Local PyPI mirror | HTTP/8080 (configurable) | pip/poetry install | Yes |
| Developer workstation | Module target APIs | Varies by module | Testing actions (e.g., TheHive, HTTP endpoints) | Yes |
| Docker container | Module target APIs | Varies by module | Action execution | Yes |

**Example module-specific flows:**

**TheHiveV5 Module:**
- Destination: TheHive instance
- Port: HTTPS/443 (or configured port)
- Protocol: HTTPS/REST API
- Purpose: Create alerts, add comments, etc.

**HTTP Module:**
- Destination: Target API endpoints
- Port: HTTP/80 or HTTPS/443 (configurable)
- Protocol: HTTP/HTTPS
- Purpose: Make HTTP requests

**Microsoft 365 Module (example):**
- Destination: `graph.microsoft.com`
- Port: HTTPS/443
- Protocol: HTTPS/REST API
- Purpose: Microsoft Graph API calls
- **Note**: Requires internet access unless you have an on-premises Microsoft deployment

##### Network Security Considerations

**Firewall rules needed (Standard Environment):**

```bash
# Outbound HTTPS to Docker Hub and PyPI
ALLOW tcp/443 from <docker-host> to registry-1.docker.io
ALLOW tcp/443 from <docker-host> to auth.docker.io
ALLOW tcp/443 from <docker-host> to production.cloudflare.docker.com
ALLOW tcp/443 from <docker-host> to pypi.org
ALLOW tcp/443 from <docker-host> to files.pythonhosted.org

# DNS resolution
ALLOW udp/53 from <docker-host> to <dns-server>
```

**Proxy configuration (if required):**

If your environment uses an HTTP/HTTPS proxy:

```bash
# Set proxy environment variables BEFORE building
export HTTP_PROXY="http://proxy.company.com:8080"
export HTTPS_PROXY="http://proxy.company.com:8080"
export NO_PROXY="localhost,127.0.0.1"

# Docker daemon proxy configuration
# Edit /etc/docker/daemon.json
{
  "proxies": {
    "http-proxy": "http://proxy.company.com:8080",
    "https-proxy": "http://proxy.company.com:8080",
    "no-proxy": "localhost,127.0.0.1"
  }
}

# Restart Docker
sudo systemctl restart docker

# Then proceed with setup
bash .docker/setup-module.sh ./YourModule
```

**SSL/TLS Inspection:**

If your network performs SSL/TLS inspection:

1. **Import corporate CA certificates:**
```bash
# Copy corporate CA certificate
sudo cp corporate-ca.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates

# For Docker builds, add to Dockerfile:
COPY corporate-ca.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates
```

2. **Configure pip for custom CA:**
```bash
# In Dockerfile before pip/poetry commands
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
```

##### Air-Gap Network Topology Example

```
┌─────────────────────────────────────────────────────────┐
│ Air-Gapped Network (No Internet)                        │
│                                                          │
│  ┌──────────────┐         ┌─────────────────┐          │
│  │  Developer   │  HTTP   │  Local PyPI     │          │
│  │  Workstation │────────▶│  Mirror         │          │
│  │              │  :8080  │  (offline pkgs) │          │
│  └──────┬───────┘         └─────────────────┘          │
│         │                                                │
│         │ Docker build                                   │
│         ▼                                                │
│  ┌──────────────┐                                       │
│  │ Docker       │         ┌─────────────────┐          │
│  │ Engine       │  HTTPS  │  TheHive /      │          │
│  │ (local imgs) │────────▶│  Target APIs    │          │
│  └──────────────┘  :443   └─────────────────┘          │
│                                                          │
└─────────────────────────────────────────────────────────┘

No outbound internet flows ✓
All dependencies pre-loaded ✓
```

##### Bandwidth Planning

**Initial setup (internet-connected):**
- Per module first build: 1-2 GB download
- Subsequent builds: ~50-100 MB (cache hits)

**Air-gap transfer:**
- One-time transfer: 2-5 GB (base images + packages + modules)
- Updates (periodic): ~500 MB - 1 GB (new packages only)

**Runtime (action execution):**
- Minimal: <1 MB per action (API calls only)
- Depends entirely on module's target API responses

##### Troubleshooting Network Issues

**Cannot pull Docker images:**
```bash
# Test connectivity
curl -v https://registry-1.docker.io/v2/
curl -v https://auth.docker.io/token

# Check DNS
nslookup registry-1.docker.io
dig registry-1.docker.io

# Verify proxy settings
echo $HTTP_PROXY
echo $HTTPS_PROXY

# Check Docker daemon logs
sudo journalctl -u docker --no-pager | tail -50
```

**Pip/Poetry fails to download packages:**
```bash
# Test PyPI connectivity
curl -v https://pypi.org/simple/

# Test specific package
curl -v https://files.pythonhosted.org/packages/

# Check pip configuration
pip config list

# Verbose pip install to see errors
pip install -v <package-name>
```

**Local PyPI mirror not accessible (air-gap):**
```bash
# Check if server is running
ps aux | grep "python.*http.server"
netstat -tlnp | grep 8080

# Test from same machine
curl http://localhost:8080/simple/

# Test from Docker container
docker run --rm --add-host=host.docker.internal:host-gateway python:3.11 \
  curl http://host.docker.internal:8080/simple/
```

**Module fails to connect to target API:**
```bash
# From host machine
curl -v https://your-thehive-instance.com/api/v1/status

# From Docker container (test network)
make shell
# Inside container:
curl -v https://your-thehive-instance.com/api/v1/status

# Check DNS resolution in container
nslookup your-thehive-instance.com
```

##### Network Requirements Summary Table

| Environment | Docker Hub | PyPI | Module APIs | Internet Required |
|-------------|-----------|------|-------------|-------------------|
| **Standard** | ✅ Yes (build) | ✅ Yes (build) | ✅ Yes (runtime) | ✅ Yes |
| **Air-gap** | ❌ No (pre-loaded) | ❌ No (local mirror) | ✅ Yes (runtime) | ❌ No |
| **Proxy** | ✅ Yes (via proxy) | ✅ Yes (via proxy) | ✅ Yes (runtime) | ⚠️ Via proxy |

> **📝 Note for Air-Gapped Environments**: If you're deploying on an isolated VM without internet access, see the complete [🔒 Air-Gapped Environment Setup](#-air-gapped-environment-setup) section at the end of this document.

## 🚀 Quick Start

### 1. Setup a Module

```bash
cd sekoia-automation-library
bash .docker/setup-module.sh ./HTTP
```

> **Note on Permissions**: The script automatically configures UID/GID mapping in the `.env` file so that files created by Docker belong to your local user (not root). This prevents permission issues on result files.

### 2. Configure Parameters

Edit the generated configuration files:
```bash
cd HTTP

# Module configuration (API keys, URLs, etc.)
nano config/module_configuration.json

# Arguments for a specific action
nano config/request_args.json
```

### 3. Build and Run

```bash
# Build the Docker image
make build

# List available actions
make list-actions

# Run an action
make run ACTION=request

# View results
cat results/action_results.json | jq .
```

## 📁 Structure Created by Setup

```
ModuleName/
├── Makefile                          # Standardized commands
├── docker-compose.local.yml          # Docker configuration
├── Dockerfile                        # Docker image definition (optional)
├── main.py.original                 # Original main.py (backup)
├── .env                              # Environment variables
├── .dockerignore                     # Files excluded from build
├── config/                           # 📝 Customize these
│   ├── module_configuration.json     # Module config
│   ├── action1_args.json             # Action 1 arguments
│   └── action2_args.json             # Action 2 arguments
├── symphony/                         # 🤖 Auto-generated
│   ├── token
│   ├── url_callback
│   ├── trigger_configuration.json
│   ├── module_configuration          # Copied from config/
│   └── arguments                     # Copied from config/
└── results/                          # 📊 Execution results
    └── action_results.json
```

## 🛠️ Makefile Commands

| Command | Description |
|---------|-------------|
| `make help` | Display help |
| `make setup` | Create necessary files |
| `make build` | Build the Docker image |
| `make rebuild` | Rebuild without cache |
| `make run ACTION=<name>` | Run an action |
| `make shell` | Open a shell in the container |
| `make list-actions` | List available actions |
| `make check-config` | Verify configuration |
| `make clean` | Clean results |
| `make clean-all` | Clean everything (including image) |

## 📖 Usage Examples

### Example 1: HTTP Module

```bash
# Setup
bash .docker/setup-module.sh ./HTTP
cd HTTP

# Create request configuration
cat > config/request_args.json << 'EOF'
{
  "url": "https://api.github.com/repos/SEKOIA-IO/sekoia-automation-sdk",
  "method": "GET"
}
EOF

# Execute
make build
make run ACTION=request

# View results
cat results/action_results.json | jq .
```

### Example 2: TheHiveV5 Module

```bash
# Setup
bash .docker/setup-module.sh ./TheHiveV5
cd TheHiveV5

# Module configuration
cat > config/module_configuration.json << 'EOF'
{
  "base_url": "https://thehive.example.com",
  "apikey": "your-api-key-here",
  "organisation": "your-org"
}
EOF

# Action configuration
cat > config/thehive_create_alert_args.json << 'EOF'
{
  "alert": {
    "title": "Test Alert",
    "type": "test",
    "source": "local-test",
    "description": "Test alert from local Docker"
  }
}
EOF

# Execute
make build
make run ACTION=thehive_create_alert

# View results
cat results/action_results.json | jq .
```

## 🔧 Configuration Files

### .env - Environment Variables

Auto-generated with:
```bash
MODULE_NAME=HTTP
MODULE_NAME_LOWER=http
LOG_LEVEL=DEBUG
PLAYBOOK_RUN_ID=local-test-run
MAIN_SCRIPT=main.py

# User/Group mapping (auto-detected)
USER_ID=1000  # Your local UID
GROUP_ID=1000 # Your local GID
```

> **Important**: Files created in `results/` will belong to your user thanks to UID/GID mapping.

### config/module_configuration.json

**✨ Auto-generated** from `manifest.json` with intelligent examples!

Example for TheHiveV5:
```json
{
  "base_url": "https://your-instance.example.com",
  "apikey": "<your-apikey>",
  "organisation": "<user organisation>"
}
```

Example for CrowdStrike:
```json
{
  "aws_access_key_id": "<identifier of the access key>",
  "aws_secret_access_key": "<your-aws_secret_access_key>",
  "aws_region": "<area hosting the AWS resources>"
}
```

> **Note**: Fields are extracted from `manifest.json` with:
> - Placeholders based on descriptions
> - Special marking for secrets (e.g., `<your-apikey>`)
> - Pre-filled URLs for URI-type fields

### config/<action>_args.json

Action-specific arguments (auto-generated with examples):

```json
{
  "param1": "value1",
  "param2": "value2"
}
```

## 🎯 Development Workflow

1. **Initial Setup**
   ```bash
   bash .docker/setup-module.sh ./YourModule
   cd YourModule
   ```

2. **Configuration**
   - Edit `config/module_configuration.json`
   - Edit `config/<action>_args.json` for each action

3. **Iterative Development**
   ```bash
   # After code modifications
   make rebuild
   make run ACTION=your_action

   # Check results
   cat results/action_results.json | jq .
   ```

4. **Debugging**
   ```bash
   # Open a shell in the container
   make shell

   # Run manually with debug wrapper
   python main_debug.py your_action
   ```

## 🔍 Troubleshooting

### No results displayed

```bash
# Check result files
ls -la results/

# Run in debug mode
make run ACTION=your_action

# Check the saved results
cat results/action_results.json | jq .
```

### Configuration error

```bash
# Verify configuration
make check-config

# Check that files exist
ls -la config/
```

### Rebuild required

```bash
# After code or dependency modifications
make rebuild
```

### "Invalid URL" error but no results

The patched main.py automatically handles this:

```bash
# Results are always saved even if callback fails
make run ACTION=your_action

# Check the saved results
cat results/action_results.json | jq .
```

## 🧹 Cleanup

### Clean a module configuration

```bash
bash .docker/setup-module.sh --clean ./HTTP
```

**Removes**:
- `Makefile`, `docker-compose.local.yml`, `Dockerfile`, `main_debug.py`, `.env`, `.dockerignore`
- `.backup` files
- `symphony/`, `results/`, `config/` directories
- Entries added to `.gitignore`

## 📝 Important Notes

- `config/`, `symphony/`, and `results/` directories are in `.gitignore`
- The `.env` file contains local environment variables
- Symphony tokens are dummies for local testing
- Results are stored in `results/` as JSON files
- **Always use `run-debug` for local testing** to ensure results are saved

## 🔄 Migration from Old System

If you already have a Makefile or docker-compose:

```bash
# The script automatically creates backups
bash .docker/setup-module.sh ./YourModule

# Backups are created with .backup extension
ls -la YourModule/*.backup
```

## 🎨 Customization

### Change log level

```bash
# In the .env file
LOG_LEVEL=INFO  # or DEBUG, WARNING, ERROR
```

### Add environment variables

```bash
# Edit .env
echo "CUSTOM_VAR=value" >> .env

# Edit docker-compose.local.yml to expose them
```

## 📚 Additional Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Quick start guide with examples
- **[DEBUG_MODE.md](DEBUG_MODE.md)** - Detailed explanation of debug mode
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and changes

## 🤝 Contributing

To improve this standardized solution:

1. Propose modifications to the templates
2. Test on multiple modules
3. Document specific use cases
4. Submit pull requests

---

## 🔒 Air-Gapped Environment Setup

**For isolated environments without internet access**

This section provides complete instructions for deploying and using this development kit on Linux VMs in air-gapped environments (no internet access).

For **completely isolated Linux VMs without internet access**, you must prepare the following **BEFORE** deploying to the air-gapped environment:

#### 1. Docker Images to Export

Export all required base images on a machine with internet access:

```bash
# Pull all required images
docker pull python:3.11
docker pull python:3.10
docker pull python:3.9

# Export images to tar files
docker save python:3.11 -o python-3.11.tar
docker save python:3.10 -o python-3.10.tar
docker save python:3.9 -o python-3.9.tar

# Calculate checksums for integrity verification
sha256sum python-*.tar > docker-images.sha256
```

**Size estimation**: ~900 MB per Python image (compressed)

#### 2. Python Packages (PyPI Dependencies)

Download all Python packages required by your modules:

```bash
# Create a directory for offline packages
mkdir -p offline-packages

# Download packages for a specific module
# (Repeat for each module you need)
cd YourModule
pip download -d ../offline-packages -r requirements.txt

# OR use poetry
poetry export -f requirements.txt --output requirements.txt --without-hashes
pip download -d ../offline-packages -r requirements.txt

# Create a package index
cd ../offline-packages
pip install pip2pi
dir2pi .
```

**Alternative**: Use a PyPI mirror tool like `bandersnatch` or `devpi`

#### 3. System Dependencies

Identify and download system packages (Debian/Ubuntu example):

```bash
# On the internet-connected machine:
# Download packages with dependencies
apt-get download \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    build-essential \
    pkg-config

# Download to a specific directory
mkdir -p offline-apt-packages
cd offline-apt-packages

# Use apt-offline or download manually
apt-get --download-only --print-uris install gcc g++ make libffi-dev libssl-dev | \
    grep -oP "(?<=')http[^']+(?=')" | \
    xargs -n 1 wget

# Create SHA256 checksums
sha256sum *.deb > packages.sha256
```

#### 4. Development Kit Files

Ensure you have all these files from this repository:

```bash
# Transfer the entire .docker directory
.docker/
├── setup-module.sh           # Main setup script
├── docker-helper.sh          # Helper commands
├── *.template                # All template files
└── *.md                      # Documentation

# AND the module directories you need
YourModule/
├── main.py
├── manifest.json
├── action_*.json
├── pyproject.toml
├── poetry.lock
└── [module code]
```

#### 5. Transfer Package

Create a complete transfer package:

```bash
# On internet-connected machine
mkdir -p sekoia-devkit-offline
cd sekoia-devkit-offline

# Copy everything
cp -r /path/to/.docker/ .
cp -r /path/to/YourModule/ .
cp /path/to/docker-images/*.tar .
cp /path/to/docker-images.sha256 .
cp -r /path/to/offline-packages/ .
cp -r /path/to/offline-apt-packages/ .

# Create transfer archive
cd ..
tar -czf sekoia-devkit-offline.tar.gz sekoia-devkit-offline/

# Calculate final checksum
sha256sum sekoia-devkit-offline.tar.gz > sekoia-devkit-offline.sha256
```

**Total size estimation**: 2-5 GB depending on modules

#### 6. Air-Gapped Installation Steps

On the air-gapped Linux VM:

**Step 1: Verify transfer integrity**
```bash
sha256sum -c sekoia-devkit-offline.sha256
tar -xzf sekoia-devkit-offline.tar.gz
cd sekoia-devkit-offline
```

**Step 2: Install system dependencies**
```bash
# Verify package checksums
cd offline-apt-packages
sha256sum -c packages.sha256

# Install packages
sudo dpkg -i *.deb

# Fix any dependency issues
sudo apt-get install -f  # If available, otherwise manual resolution needed
```

**Step 3: Load Docker images**
```bash
# Verify image checksums
sha256sum -c docker-images.sha256

# Load images
docker load -i python-3.11.tar
docker load -i python-3.10.tar
docker load -i python-3.9.tar

# Verify loaded images
docker images | grep python
```

**Step 4: Setup local PyPI mirror**
```bash
# Option A: Simple directory server
cd offline-packages
python3 -m http.server 8080 &

# Configure pip to use local mirror
mkdir -p ~/.pip
cat > ~/.pip/pip.conf << EOF
[global]
index-url = http://localhost:8080/simple
trusted-host = localhost
EOF

# Option B: Use pip install with --no-index
# (Specify in module's setup)
```

**Step 5: Configure modules**
```bash
# Setup a module
bash .docker/setup-module.sh ./YourModule
cd YourModule

# Configure to use offline packages
# Edit Dockerfile to include:
# --index-url http://host.docker.internal:8080/simple
# --trusted-host host.docker.internal
# OR copy offline-packages into module and use --no-index
```

**Step 6: Build with offline packages**

Modify the `Dockerfile` to use offline packages:

```dockerfile
# Add to Dockerfile before poetry install
COPY offline-packages /offline-packages
RUN pip install --no-index --find-links=/offline-packages poetry

# OR configure poetry to use local index
RUN poetry config repositories.local http://host.docker.internal:8080/simple
RUN poetry config http-basic.local "" ""
```

**Step 7: Build and test**
```bash
# Build image (uses local packages only)
make build

# Test execution
make run ACTION=your_action
```

#### 7. Air-Gap Considerations

**Important notes for air-gapped environments:**

- ✅ **No automatic updates**: All packages frozen at transfer time
- ✅ **Manual certificate management**: Copy SSL/TLS certificates if needed
- ✅ **DNS configuration**: May need local DNS or `/etc/hosts` entries
- ✅ **Time synchronization**: Ensure NTP or manual time sync for logs
- ✅ **Storage**: Plan for image layers and build cache (~10-20 GB recommended)
- ⚠️ **Security updates**: Establish process for periodic offline updates
- ⚠️ **New modules**: Require new offline package downloads

#### 8. Troubleshooting Air-Gap Issues

**Docker fails to build**
```bash
# Check loaded images
docker images

# Verify Dockerfile base image matches loaded image
grep "FROM" Dockerfile
```

**Pip/Poetry fails to install packages**
```bash
# Test local package server
curl http://localhost:8080/simple/

# List available packages
ls offline-packages/

# Manual install test
pip install --no-index --find-links=offline-packages <package-name>
```

**Missing system dependencies**
```bash
# Check what's needed
ldd /path/to/binary

# Identify missing packages
dpkg -S /path/to/missing/library
```

#### 9. Alternative: Pre-built Images

For maximum simplicity in air-gap, consider:

1. **Build complete images** on internet-connected machine
2. **Export built images** instead of base images
3. **Transfer and load** ready-to-use images

```bash
# On internet-connected machine
cd YourModule
docker build -t yourmodule:offline .
docker save yourmodule:offline -o yourmodule-offline.tar

# On air-gapped machine
docker load -i yourmodule-offline.tar
# Ready to use, no build needed
```

## 📄 License

This development kit is part of the Sekoia Automation Library.
