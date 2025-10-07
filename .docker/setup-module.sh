#!/bin/bash

# Standardized configuration script for Sekoia Automation modules
# Usage:
#   ./setup-module.sh <module_path>           - Configure a module
#   ./setup-module.sh --clean <module_path>   - Clean module configuration

set -e

# Colors for messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Display functions
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Cleanup function
clean_module() {
    local module_path="$1"

    print_info "🧹 Cleaning module: $(basename "$module_path")"
    echo ""

    # Restore original main.py if backup exists
    if [ -f "$module_path/main.py.original" ]; then
        print_info "Restoring original main.py..."
        mv "$module_path/main.py.original" "$module_path/main.py"
        print_success "Restored: main.py (from backup)"
    fi

    # Restore original Dockerfile if backup exists
    if [ -f "$module_path/Dockerfile.backup" ]; then
        print_info "Restoring original Dockerfile..."
        mv "$module_path/Dockerfile.backup" "$module_path/Dockerfile"
        print_success "Restored: Dockerfile (from backup)"
    elif [ -f "$module_path/Dockerfile" ]; then
        # If no backup exists but Dockerfile was created by setup, check if it's from template
        if grep -q "# Standardized Dockerfile for Sekoia Automation modules" "$module_path/Dockerfile" 2>/dev/null; then
            rm -f "$module_path/Dockerfile"
            print_success "Removed: Dockerfile (created by setup)"
        fi
    fi

    # List of files to remove (that were created by setup)
    local files_to_remove=(
        "Makefile"
        "docker-compose.local.yml"
        ".env"
        ".dockerignore"
    )

    # Remove files
    for file in "${files_to_remove[@]}"; do
        if [ -f "$module_path/$file" ]; then
            rm -f "$module_path/$file"
            print_success "Removed: $file"
        fi

        # Remove backups that might have been left behind
        if [ -f "$module_path/${file}.backup" ]; then
            rm -f "$module_path/${file}.backup"
            print_success "Removed: ${file}.backup"
        fi
    done

    # Remove directories created by setup
    local dirs_to_remove=(
        "symphony"
        "results"
        "config"
    )

    for dir in "${dirs_to_remove[@]}"; do
        if [ -d "$module_path/$dir" ]; then
            rm -rf "$module_path/$dir"
            print_success "Removed: $dir/"
        fi
    done

    # Handle .gitignore
    if [ -f "$module_path/.gitignore" ]; then
        local docker_section_exists=$(grep -c "# Local Docker development" "$module_path/.gitignore" 2>/dev/null || echo "0")

        if [ "$docker_section_exists" -gt 0 ]; then
            # Count lines before and after our section
            local lines_before=$(awk '/# Local Docker development/{exit} {count++} END{print count+0}' "$module_path/.gitignore")
            local lines_after=$(awk 'found{print} /^$/&&prev~/^docker-compose.local.yml.backup$/{found=1} {prev=$0}' "$module_path/.gitignore" | wc -l)

            # If .gitignore was created by setup (only contains our section)
            if [ "$lines_before" -eq 0 ] && [ "$lines_after" -eq 0 ]; then
                rm -f "$module_path/.gitignore"
                print_success "Removed: .gitignore (was created by setup)"
            else
                # Remove only the "Local Docker development" section
                {
                    awk '
                        /# Local Docker development/ { in_section=1; next }
                        in_section && /^$/ { in_section=0; next }
                        !in_section { print }
                    ' "$module_path/.gitignore" > "$module_path/.gitignore.tmp" 2>/dev/null && \
                    mv "$module_path/.gitignore.tmp" "$module_path/.gitignore" 2>/dev/null
                } || {
                    print_warning "Cannot clean .gitignore (insufficient permissions)"
                    rm -f "$module_path/.gitignore.tmp" 2>/dev/null
                    return
                }
                print_success "Cleaned: .gitignore (removed Docker section)"
            fi
        fi
    fi

    echo ""
    print_success "✨ Cleanup completed for module $(basename "$module_path")"
    print_info "Module has been restored to its initial state"
}

# Check arguments
if [ -z "$1" ]; then
    print_error "Usage: $0 [--clean] <module_path>"
    echo ""
    echo "Examples:"
    echo "  $0 ./HTTP              - Configure HTTP module"
    echo "  $0 --clean ./HTTP      - Clean HTTP module configuration"
    exit 1
fi

# Handle --clean option
if [ "$1" = "--clean" ]; then
    if [ -z "$2" ]; then
        print_error "Usage: $0 --clean <module_path>"
        exit 1
    fi

    MODULE_PATH=$(realpath "$2")

    if [ ! -d "$MODULE_PATH" ]; then
        print_error "Module $MODULE_PATH does not exist"
        exit 1
    fi

    clean_module "$MODULE_PATH"
    exit 0
fi

MODULE_PATH=$(realpath "$1")
MODULE_NAME=$(basename "$MODULE_PATH")
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if module exists
if [ ! -d "$MODULE_PATH" ]; then
    print_error "Module $MODULE_PATH does not exist"
    exit 1
fi

print_info "Configuring module: $MODULE_NAME"
print_info "Path: $MODULE_PATH"
echo ""

# Create necessary directories
print_info "Creating directories..."
mkdir -p "$MODULE_PATH/config"
mkdir -p "$MODULE_PATH/symphony"
mkdir -p "$MODULE_PATH/results"
print_success "Directories created"

# Copy Makefile
print_info "Installing standardized Makefile..."
if [ -f "$MODULE_PATH/Makefile" ]; then
    print_warning "Existing Makefile detected, backing up to Makefile.backup"
    cp "$MODULE_PATH/Makefile" "$MODULE_PATH/Makefile.backup"
fi
cp "$SCRIPT_DIR/Makefile.template" "$MODULE_PATH/Makefile"
print_success "Makefile installed"

# Copy docker-compose
print_info "Installing standardized docker-compose..."
if [ -f "$MODULE_PATH/docker-compose.local.yml" ]; then
    print_warning "Existing docker-compose.local.yml detected, backing up to docker-compose.local.yml.backup"
    cp "$MODULE_PATH/docker-compose.local.yml" "$MODULE_PATH/docker-compose.local.yml.backup"
fi
cp "$SCRIPT_DIR/docker-compose.local.yml.template" "$MODULE_PATH/docker-compose.local.yml"
print_success "docker-compose.local.yml installed"

# Automatically backup and install standardized Dockerfile
if [ ! -f "$MODULE_PATH/Dockerfile" ]; then
    print_info "No Dockerfile detected, installing standardized Dockerfile..."
    cp "$SCRIPT_DIR/Dockerfile.template" "$MODULE_PATH/Dockerfile"
    print_success "Standardized Dockerfile installed"
else
    print_info "Existing Dockerfile detected, backing up and installing standardized version..."
    cp "$MODULE_PATH/Dockerfile" "$MODULE_PATH/Dockerfile.backup"
    cp "$SCRIPT_DIR/Dockerfile.template" "$MODULE_PATH/Dockerfile"
    print_success "Dockerfile replaced (backup created as Dockerfile.backup)"
    print_info "Note: The standardized Dockerfile supports USER_ID and GROUP_ID arguments"
fi

# Backup original main.py and create patched version
print_info "Creating patched main.py for local development..."
if [ -f "$MODULE_PATH/main.py" ]; then
    # Backup original main.py
    cp "$MODULE_PATH/main.py" "$MODULE_PATH/main.py.original"
    print_info "Original main.py backed up to main.py.original"

    # Extract imports and registrations from main.py
    IMPORTS=$(grep -E "^from .* import " "$MODULE_PATH/main.py" | grep -v "from sekoia_automation.module import Module")
    REGISTERS=$(grep "module.register" "$MODULE_PATH/main.py")

    # Create patched main.py with Python to avoid escaping issues
    python3 - "$SCRIPT_DIR/main.py.template" "$MODULE_PATH/main.py" "$MODULE_PATH/main.py.original" << 'PYTHON_EOF'
import sys
import re

template_file = sys.argv[1]
output_file = sys.argv[2]
main_file = sys.argv[3]

# Read template
with open(template_file, 'r') as f:
    content = f.read()

# Read main.py to extract imports and registers
with open(main_file, 'r') as f:
    main_content = f.read()

# Extract imports (exclude Module)
import_lines = [line for line in main_content.split('\n')
                if line.startswith('from ') and 'import' in line
                and 'sekoia_automation.module' not in line]
imports = '\n    '.join(import_lines)  # Indent with 4 spaces

# Extract registrations
register_lines = [line.strip() for line in main_content.split('\n')
                  if 'module.register' in line]
registers = '\n    '.join(register_lines)  # Indent with 4 spaces

# Replace placeholders
content = content.replace('{{IMPORT_ACTIONS}}', imports)
content = content.replace('{{REGISTER_ACTIONS}}', registers)

# Write file
with open(output_file, 'w') as f:
    f.write(content)
PYTHON_EOF

    chmod +x "$MODULE_PATH/main.py"
    print_success "Patched main.py created (original backed up as main.py.original)"
else
    print_warning "main.py not found, patched version not created"
fi

# Create .env file
print_info "Creating .env file..."
# Convert module name to lowercase for Docker
MODULE_NAME_LOWER=$(echo "$MODULE_NAME" | tr '[:upper:]' '[:lower:]')
cat > "$MODULE_PATH/.env" << EOF
# Configuration for module $MODULE_NAME
MODULE_NAME=$MODULE_NAME
MODULE_NAME_LOWER=$MODULE_NAME_LOWER
LOG_LEVEL=DEBUG
PLAYBOOK_RUN_ID=local-test-run

# User/Group mapping to avoid permission issues
USER_ID=$(id -u)
GROUP_ID=$(id -g)
EOF
print_success ".env file created with UID=$(id -u) and GID=$(id -g)"

# Create symphony files
print_info "Creating symphony files..."
echo "dummy-token-for-local-testing" > "$MODULE_PATH/symphony/token"
echo "" > "$MODULE_PATH/symphony/url_callback"
echo '{}' > "$MODULE_PATH/symphony/trigger_configuration.json"
print_success "Symphony files created"

# Function to generate module_configuration.json from manifest.json
generate_module_config() {
    local manifest_file="$1"

    # Check if python3 is available
    if ! command -v python3 &> /dev/null; then
        echo '{}'
        return
    fi

    # Extract configuration from manifest and create an example
    python3 - "$manifest_file" << 'PYTHON_EOF'
import json
import sys

manifest_file = sys.argv[1]

try:
    with open(manifest_file, 'r') as f:
        manifest = json.load(f)

    configuration = manifest.get('configuration', {})
    properties = configuration.get('properties', {})
    required = configuration.get('required', [])
    secrets = configuration.get('secrets', [])

    example = {}

    # If no properties, return empty object
    if not properties:
        print('{}')
        sys.exit(0)

    # Generate examples for required fields
    for field in required:
        if field in properties:
            prop = properties[field]
            prop_type = prop.get('type', 'string')
            description = prop.get('description', '')

            # Mark secrets
            is_secret = field in secrets

            if prop_type == 'string':
                if 'format' in prop and prop['format'] == 'uri':
                    example[field] = 'https://your-instance.example.com'
                elif is_secret:
                    example[field] = f'<your-{field}>'
                else:
                    # Use description as placeholder
                    placeholder = description.replace('Your ', '').replace('The ', '').replace('An ', '').replace('A ', '')
                    example[field] = f'<{placeholder[:60]}>' if description else f'<{field}>'
            elif prop_type == 'object':
                example[field] = {}
            elif prop_type == 'integer':
                example[field] = prop.get('default', 0)
            elif prop_type == 'number':
                example[field] = prop.get('default', 0.0)
            elif prop_type == 'boolean':
                example[field] = prop.get('default', True)
            elif prop_type == 'array':
                example[field] = []

    # Add optional fields with default value
    for field, prop in properties.items():
        if field not in example and 'default' in prop:
            example[field] = prop['default']

    print(json.dumps(example, indent=2, ensure_ascii=False))
except Exception as e:
    print('{}')
PYTHON_EOF
}

# Create module configuration file if absent
if [ ! -f "$MODULE_PATH/config/module_configuration.json" ]; then
    print_info "Creating config/module_configuration.json..."

    # Check if manifest.json exists
    if [ -f "$MODULE_PATH/manifest.json" ]; then
        module_config=$(generate_module_config "$MODULE_PATH/manifest.json")

        if [ -n "$module_config" ] && [ "$module_config" != "{}" ]; then
            echo "$module_config" > "$MODULE_PATH/config/module_configuration.json"
            print_success "File created with example based on manifest.json"
        else
            echo '{}' > "$MODULE_PATH/config/module_configuration.json"
            print_success "File created (no configuration in manifest.json)"
        fi
    else
        echo '{}' > "$MODULE_PATH/config/module_configuration.json"
        print_success "File created (manifest.json not found)"
    fi
else
    print_info "config/module_configuration.json already exists"
fi

# Function to generate example configuration from JSON schema
generate_example_config() {
    local action_file="$1"
    local action_name="$2"

    # Check if python3 is available
    if ! command -v python3 &> /dev/null; then
        echo '{}'
        return
    fi

    # Extract required properties and create an example
    python3 - "$action_file" << 'PYTHON_EOF'
import json
import sys

action_file = sys.argv[1]

try:
    with open(action_file, 'r') as f:
        schema = json.load(f)

    arguments = schema.get('arguments', {})
    properties = arguments.get('properties', {})
    required = arguments.get('required', [])

    example = {}

    # Generate examples for required fields
    for field in required:
        if field in properties:
            prop = properties[field]
            prop_type = prop.get('type', 'string')
            description = prop.get('description', '')

            if prop_type == 'string':
                if 'format' in prop and prop['format'] == 'uri':
                    example[field] = 'https://example.com/api/endpoint'
                elif 'enum' in prop:
                    example[field] = prop['enum'][0] if prop['enum'] else ''
                else:
                    # Use description as placeholder
                    example[field] = f'<{description[:50]}>' if description else f'<{field}>'
            elif prop_type == 'object':
                example[field] = {}
            elif prop_type == 'integer':
                example[field] = prop.get('default', 0)
            elif prop_type == 'number':
                example[field] = prop.get('default', 0.0)
            elif prop_type == 'boolean':
                example[field] = prop.get('default', True)
            elif prop_type == 'array':
                example[field] = []

    # Add some common optional fields with their default value
    common_optional = ['headers', 'verify_ssl', 'timeout']
    for field in common_optional:
        if field in properties and field not in example:
            prop = properties[field]
            if 'default' in prop:
                example[field] = prop['default']

    print(json.dumps(example, indent=2, ensure_ascii=False))
except Exception as e:
    print('{}')
PYTHON_EOF
}

# Detect available actions
print_info "Detecting available actions..."
cd "$MODULE_PATH"

if ! ls action_*.json 1> /dev/null 2>&1; then
    print_warning "No actions detected (action_*.json files)"
else
    print_success "Actions detected:"
    for action_file in action_*.json; do
        if [ -f "$action_file" ]; then
            # Extract docker_parameters from JSON (actual command name)
            docker_cmd=$(grep -o '"docker_parameters"[[:space:]]*:[[:space:]]*"[^"]*"' "$action_file" | head -1 | sed 's/.*: *"\(.*\)".*/\1/')
            action_name=$(grep -o '"name"[[:space:]]*:[[:space:]]*"[^"]*"' "$action_file" | head -1 | sed 's/.*: *"\(.*\)".*/\1/')

            if [ -n "$docker_cmd" ]; then
                echo "  - $action_name"
                echo "    → config/${docker_cmd}_args.json"

                # Create args file with docker command name if absent
                if [ ! -f "config/${docker_cmd}_args.json" ]; then
                    print_info "Creating config/${docker_cmd}_args.json with example..."

                    # Generate example based on schema
                    example_config=$(generate_example_config "$action_file" "$docker_cmd")

                    if [ -n "$example_config" ] && [ "$example_config" != "{}" ]; then
                        echo "$example_config" > "config/${docker_cmd}_args.json"
                        print_success "File created with example based on schema"
                    else
                        echo '{}' > "config/${docker_cmd}_args.json"
                        print_success "File created (needs customization)"
                    fi
                fi
            fi
        fi
    done
fi

# Create .dockerignore if absent
if [ ! -f "$MODULE_PATH/.dockerignore" ]; then
    print_info "Creating .dockerignore..."
    cat > "$MODULE_PATH/.dockerignore" << EOF
.git
.gitignore
.dockerignore
symphony/
config/
results/
*.md
.env
Makefile
docker-compose*.yml
EOF
    print_success ".dockerignore created"
fi

# Add .gitignore for local files
print_info "Updating .gitignore..."

# Check if file exists and is writable
if [ ! -f "$MODULE_PATH/.gitignore" ]; then
    touch "$MODULE_PATH/.gitignore" 2>/dev/null || {
        print_warning "Cannot create .gitignore (permissions)"
        echo ""
        print_success "✨ Configuration completed for module $MODULE_NAME"
        echo ""
        echo "📖 Next steps:"
        echo "  1. cd $MODULE_PATH"
        echo "  2. Edit config/module_configuration.json with your parameters"
        echo "  3. Edit config/<action>_args.json for your actions"
        echo "  4. make build"
        echo "  5. make run ACTION=<action_name>"
        echo ""
        echo "Available commands:"
        echo "  make help          - Display help"
        echo "  make list-actions  - List available actions"
        exit 0
    }
fi

# Check if section already exists
if ! grep -q "# Local Docker development" "$MODULE_PATH/.gitignore" 2>/dev/null; then
    # Try to add to .gitignore
    {
        cat >> "$MODULE_PATH/.gitignore" << 'EOF'

# Local Docker development
symphony/
results/
config/module_configuration.json
config/*_args.json
.env
Makefile.backup
docker-compose.local.yml.backup
EOF
    } 2>/dev/null

    # Check if it succeeded
    if [ $? -eq 0 ]; then
        print_success ".gitignore updated"
    else
        print_warning "Cannot modify .gitignore (insufficient permissions)"
        print_info "Manually add this section to your .gitignore:"
        echo ""
        echo "# Local Docker development"
        echo "symphony/"
        echo "results/"
        echo "config/module_configuration.json"
        echo "config/*_args.json"
        echo ".env"
        echo "Makefile.backup"
        echo "docker-compose.local.yml.backup"
        echo ""
    fi
else
    print_info ".gitignore already configured"
fi

echo ""
print_success "✨ Configuration completed for module $MODULE_NAME"
echo ""
echo "📖 Next steps:"
echo "  1. cd $MODULE_PATH"
echo "  2. Edit config/module_configuration.json with your parameters"
echo "  3. Edit config/<action>_args.json for your actions"
echo "  4. make build"
echo "  5. make run ACTION=<action_name>"
echo ""
echo "Available commands:"
echo "  make help          - Display help"
echo "  make list-actions  - List available actions"
