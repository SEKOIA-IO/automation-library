#!/bin/bash

# Helper script for common Docker commands
# Usage: ./docker-helper.sh <command> [module]

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_help() {
    echo -e "${BLUE}🐳 Docker Helper - Sekoia Automation Library${NC}"
    echo ""
    echo "Usage: $0 <command> [module]"
    echo ""
    echo "Available commands:"
    echo ""
    echo "  ${GREEN}setup${NC} <module>      - Configure a module for Docker"
    echo "  ${GREEN}clean${NC} <module>      - Clean module configuration"
    echo "  ${GREEN}build${NC} <module>      - Build Docker image for a module"
    echo "  ${GREEN}run${NC} <module> <action> - Execute a module action"
    echo "  ${GREEN}shell${NC} <module>      - Open a shell in the container"
    echo "  ${GREEN}list${NC} <module>       - List available actions"
    echo "  ${GREEN}help${NC}               - Display this help"
    echo ""
    echo "Examples:"
    echo "  $0 setup HTTP"
    echo "  $0 build HTTP"
    echo "  $0 run HTTP request"
    echo "  $0 list HTTP"
    echo "  $0 clean HTTP"
}

# Check arguments
if [ -z "$1" ] || [ "$1" = "help" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    print_help
    exit 0
fi

COMMAND="$1"
MODULE="$2"
ACTION="$3"

# Check if module is specified
if [ -z "$MODULE" ]; then
    echo -e "${RED}❌ Error: Module not specified${NC}"
    echo ""
    print_help
    exit 1
fi

MODULE_PATH="$REPO_ROOT/$MODULE"

# Check if module exists
if [ ! -d "$MODULE_PATH" ]; then
    echo -e "${RED}❌ Error: Module '$MODULE' does not exist in $REPO_ROOT${NC}"
    exit 1
fi

# Execute command
case "$COMMAND" in
    setup)
        echo -e "${BLUE}📦 Configuring module $MODULE${NC}"
        bash "$SCRIPT_DIR/setup-module.sh" "$MODULE_PATH"
        ;;

    clean)
        echo -e "${BLUE}🧹 Cleaning module $MODULE${NC}"
        bash "$SCRIPT_DIR/setup-module.sh" --clean "$MODULE_PATH"
        ;;

    build)
        if [ ! -f "$MODULE_PATH/Makefile" ]; then
            echo -e "${RED}❌ Error: Module not configured. Run first: $0 setup $MODULE${NC}"
            exit 1
        fi
        echo -e "${BLUE}🔨 Building Docker image for $MODULE${NC}"
        cd "$MODULE_PATH" && make build
        ;;

    run)
        if [ -z "$ACTION" ]; then
            echo -e "${RED}❌ Error: Action not specified${NC}"
            echo "Usage: $0 run $MODULE <action>"
            exit 1
        fi
        if [ ! -f "$MODULE_PATH/Makefile" ]; then
            echo -e "${RED}❌ Error: Module not configured. Run first: $0 setup $MODULE${NC}"
            exit 1
        fi
        echo -e "${BLUE}🚀 Executing action '$ACTION' for $MODULE${NC}"
        cd "$MODULE_PATH" && make run ACTION="$ACTION"
        ;;

    shell)
        if [ ! -f "$MODULE_PATH/Makefile" ]; then
            echo -e "${RED}❌ Error: Module not configured. Run first: $0 setup $MODULE${NC}"
            exit 1
        fi
        echo -e "${BLUE}🐚 Opening shell for $MODULE${NC}"
        cd "$MODULE_PATH" && make shell
        ;;

    list)
        if [ ! -f "$MODULE_PATH/Makefile" ]; then
            echo -e "${RED}❌ Error: Module not configured. Run first: $0 setup $MODULE${NC}"
            exit 1
        fi
        echo -e "${BLUE}📋 Available actions for $MODULE${NC}"
        cd "$MODULE_PATH" && make list-actions
        ;;

    *)
        echo -e "${RED}❌ Unknown command: $COMMAND${NC}"
        echo ""
        print_help
        exit 1
        ;;
esac
