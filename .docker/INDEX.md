# .docker Directory Index

This directory contains the Local Development Kit for Sekoia Automation Modules.

## 📁 File Structure

```
.docker/
├── README.md                           # Main documentation
├── QUICKSTART.md                       # Quick start guide
├── CHANGELOG.md                        # Version history
├── INDEX.md                            # This file
│
├── setup-module.sh                     # Main setup script
├── docker-helper.sh                    # Helper commands (optional)
│
├── Dockerfile.template                 # Docker image template
├── docker-compose.local.yml.template   # Docker compose template
├── Makefile.template                   # Makefile template
└── main.py.template                    # Patched main.py template
```

## 📄 File Descriptions

### Documentation Files

| File | Purpose | Target Audience |
|------|---------|----------------|
| **README.md** | Complete documentation with all features | All users |
| **QUICKSTART.md** | Step-by-step getting started guide | New users |
| **CHANGELOG.md** | Version history and changes | All users |
| **INDEX.md** | This file - directory overview | All users |

### Scripts

| File | Purpose | Usage |
|------|---------|-------|
| **setup-module.sh** | Main setup script - configures a module for local development | `bash .docker/setup-module.sh ./ModuleName` |
| **docker-helper.sh** | Optional helper script for common tasks | `.docker/docker-helper.sh help` |

### Templates

| File | Purpose | Generated File |
|------|---------|----------------|
| **Dockerfile.template** | Docker image definition with UID/GID support | `ModuleName/Dockerfile` |
| **docker-compose.local.yml.template** | Docker Compose configuration | `ModuleName/docker-compose.local.yml` |
| **Makefile.template** | Standardized commands | `ModuleName/Makefile` |
| **main.py.template** | Patched main.py for local development | `ModuleName/main.py` (replaces original) |

## 🚀 Quick Start

```bash
# 1. Setup a module
bash .docker/setup-module.sh ./YourModule

# 2. Configure
cd YourModule
nano config/module_configuration.json

# 3. Build and run
make build
make run ACTION=your_action

# 4. View results
cat results/action_results.json | jq .
```

## 🔧 What Gets Generated

When you run `setup-module.sh`, it creates these files in the module directory:

### Configuration Files
- **Makefile** - Standardized commands from template
- **docker-compose.local.yml** - Docker orchestration from template
- **Dockerfile** - Image definition from template (optional)
- **main.py.original** - Backup of original main.py
- **.env** - Environment variables (UID/GID, module name, etc.)
- **.dockerignore** - Files to exclude from Docker build

### Directories
- **config/** - Module and action configurations (auto-generated with examples)
- **symphony/** - Sekoia SDK required files (dummy values for local testing)
- **results/** - Action execution results

### Config Files (Auto-generated)
- **config/module_configuration.json** - From `manifest.json`
- **config/<action>_args.json** - From action JSON schemas

## 📚 Documentation Guide

### For Getting Started
1. Read **README.md** overview
2. Follow **QUICKSTART.md** step-by-step
3. Reference **README.md** for specific features

### For Troubleshooting
1. Check **README.md** Troubleshooting section
2. Check that patched main.py is in use
3. Review **CHANGELOG.md** for recent fixes

### For Understanding
- **main.py.template** - How the SDK patches work
- **CHANGELOG.md** - What changed and why
- Template files - See exactly what gets generated

## 🧹 Cleanup

To remove all generated files and start fresh:

```bash
bash .docker/setup-module.sh --clean ./YourModule
```

This removes:
- All files listed in "What Gets Generated"
- Backup files (.backup extension)
- .gitignore entries

## 🔒 Security Notes

- ❌ No real API keys or credentials in templates
- ❌ No hardcoded URLs except examples
- ✅ All examples use placeholders like `<your-apikey>`
- ✅ All generated local files are in .gitignore
- ✅ .env file with real UIDs is not committed

## 📦 Distribution

This directory can be safely:
- ✅ Committed to public GitHub repositories
- ✅ Shared with customers
- ✅ Included in documentation
- ✅ Used as-is without modification

All sensitive data is generated locally during setup and never committed.

## 🔄 Versioning

Current version: **2.3.0**

See [CHANGELOG.md](CHANGELOG.md) for version history.

## 🤝 Contributing

To modify or improve this development kit:

1. Edit the templates in `.docker/`
2. Test on multiple modules
3. Update documentation
4. Update CHANGELOG.md
5. Submit changes

## 📞 Support

For issues or questions:
- Check **README.md** Troubleshooting section
- Verify patched main.py is in use
- Check **CHANGELOG.md** for recent changes
- Open an issue on GitHub

## License

This development kit is part of the Sekoia Automation Library.
