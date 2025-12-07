#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     setup_environment.bash
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
#
# Date:          2025-10-11
# Last Modified: 2025-12-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    This script sets up the development environment for the Juniper Canopy application.
#
#####################################################################################################################################################################################################
# Notes:
#
#     Juniper Canopy Environment Setup Script
#     This script sets up the development environment for the Juniper Canopy application
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################

# set -e  # Exit on any error

# Configuration
PROJECT_NAME="Juniper Canopy"
ENV_NAME="JuniperPython"
PROJECT_DIR="${HOME}/Development/python/JuniperCanopy/juniper_canopy"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Define Script Constants
TRUE=0
FALSE=1

DEBUG="${TRUE}"
# DEBUG="${FALSE}"

BASH_CONFIG=""

LINUX="Linux"
MACOS="Darwin"

COMMENT_REGEX="^[[:space:]]*#.*$"
CONDA_CMD="conda"
MAMBA_CMD="mamba"
CONDA_OFFSET="2"
MAMBA_OFFSET="3"

# USE_CONDA="${TRUE}"
USE_CONDA="${FALSE}"
# USE_MAMBA="$(echo "$(( ( USE_CONDA + 1 ) % 2 ))")"
USE_MAMBA="$(((USE_CONDA + 1) % 2))"

# Define Command and Offset based on package manager choice
if [[ ${USE_CONDA} == "${TRUE}" ]]; then
	CMD="${CONDA_CMD}"
	OFFSET="${CONDA_OFFSET}"
elif [[ ${USE_MAMBA} == "${TRUE}" ]]; then
	CMD="${MAMBA_CMD}"
	OFFSET="${MAMBA_OFFSET}"
else
	echo "Borked"
	exit 1
fi

OS_TYPE="$(uname -s)"
[[ ${DEBUG} == "${TRUE}" ]] && print_status "DEBUG: OS Type: ${OS_TYPE}"
if [[ ${OS_TYPE} == "${LINUX}" ]]; then
	BASH_CONFIG="/home/pcalnon/.bashrc"
	[[ ${DEBUG} == "${TRUE}" ]] && print_status "DEBUG: Bash Linux config file: ${BASH_CONFIG}"
elif [[ ${OS_TYPE} == "${MACOS}" ]]; then
	BASH_CONFIG="/Users/pcalnon/.bash_profile"
	[[ ${DEBUG} == "${TRUE}" ]] && print_status "DEBUG: Bash MacOS config file: ${BASH_CONFIG}"
else
	print_error "Unsupported OS: ${OS_TYPE}"
	exit 1
fi
[[ ${DEBUG} == "${TRUE}" ]] && print_status "DEBUG: Bash config file: ${BASH_CONFIG}"

# Function to print colored output
print_status() {
	echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
	echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
	echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
	echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    [[ ${DEBUG} == "${TRUE}" ]] && command -v "$1" || command -v "$1" >/dev/null 2>&1   # trunk-ignore(shellcheck/SC2015)
}

print_status "Starting ${PROJECT_NAME} environment setup..."

# Check if conda is installed
RESULT="$(command_exists conda)"
[[ ${DEBUG} == "${TRUE}" ]] && print_status "DEBUG: Conda check result: ${RESULT}"
if [[ ${RESULT} == "" ]]; then
	print_error "Conda is not installed or not in PATH"
	print_status "Please install Miniconda or Anaconda and try again"
	exit 1
fi
[[ ${DEBUG} == "${TRUE}" ]] && print_status "DEBUG: Conda is installed"
CONDA_VERSION="$(conda --version)"
print_success "Conda found: ${CONDA_VERSION}"

# Check if mamba is installed
RESULT="$(command_exists mamba)"
[[ ${DEBUG} == "${TRUE}" ]] && print_status "DEBUG: Mamba check result: ${RESULT}"
if [[ ${RESULT} == "" ]]; then
	print_error "Mamba is not installed or not in PATH"
	print_status "Please install Mamba and try again"
	exit 1
fi
[[ ${DEBUG} == "${TRUE}" ]] && print_status "DEBUG: Mamba is installed"
MAMBA_FOUND="$(mamba --version)"
print_success "Mamba found: ${MAMBA_FOUND}"

# Navigate to project directory
cd "${PROJECT_DIR}" || {
	print_error "Failed to navigate to project directory: ${PROJECT_DIR}"
	exit 1
}
[[ ${DEBUG} == "${TRUE}" ]] && print_status "DEBUG: Navigated to project directory"
WORKING_DIR="$(pwd || 0)"
print_status "Working in directory: ${WORKING_DIR}"

# Check if environment already exists
print_status "Check if conda environment already exists: ${ENV_NAME}"
ENV_LIST_RAW="$(eval "${CMD} env list")"
ENV_LIST_NO_COM="$(echo "${ENV_LIST_RAW}" | grep -v -e "${COMMENT_REGEX}")"
ENV_LIST="$(echo "${ENV_LIST_NO_COM}" | tail -n +"${OFFSET}")"
print_status "Existing conda environments:\n${ENV_LIST}"
print_status "Grep for environment '${ENV_NAME}' in the list above"
ENV_EXISTS=$(echo "${ENV_LIST}" | grep "${ENV_NAME}")
print_status "Grep result for environment '${ENV_NAME}': \"${ENV_EXISTS}\""
if [[ ${ENV_EXISTS} != "" || ${TRUE} == "${TRUE}" ]]; then
	print_warning "Environment '${ENV_NAME}' already exists"
	read -p "do you want to recreate it? (y/n): " -n 1 -r
	echo
	if [[ ${REPLY} =~ ^[Yy]$ ]]; then
		print_status "Removing existing environment..."
		conda env remove -n "${ENV_NAME}" -y
	else
		print_status "Using existing environment"
		conda activate "${ENV_NAME}"
		print_success "Environment activated"
		exit 0
	fi
fi

# Creating conda environment from Create conda environment YAML file
print_status "Creating conda environment from conf/conda_environment.yaml..."
if conda env create -f conf/conda_environment.yaml; then
	print_success "Conda environment created successfully"
else
	print_error "Failed to create conda environment"
	exit 1
fi

print_status "Initializing and Activating conda environment: ${ENV_NAME}..."
echo "source \"${BASH_CONFIG}\" && conda activate \"${ENV_NAME}\""
if [[ -f ${BASH_CONFIG} ]]; then
	print_status "Sourcing bash config: ${BASH_CONFIG}"
	source "${BASH_CONFIG}"    # trunk-ignore(shellcheck/SC1090)
else
	print_warning "Bash config not found: ${BASH_CONFIG}"
fi

# Try to activate the environment; ensure conda is available in this shell
if command -v conda >/dev/null 2>&1; then
	conda activate "${ENV_NAME}"
else
	print_error "Conda not found in PATH during activation"
	exit 1
fi

# Verify activation
if [[ ${CONDA_DEFAULT_ENV} != "${ENV_NAME}" ]]; then
	print_error "Failed to activate environment"
	exit 1
fi

print_success "Environment '${ENV_NAME}' activated"

# Install additional pip packages if needed
print_status "Installing additional pip packages..."
pip install -r conf/requirements.txt

# Verify key packages
print_status "Verifying key package installations..."
python -c "
import sys
packages = ['dash', 'fastapi', 'plotly', 'redis', 'torch', 'numpy', 'pandas']
failed = []

for package in packages:
    try:
        __import__(package)
        print(f'✓ {package}')
    except ImportError:
        print(f'✗ {package}')
        failed.append(package)

if failed:
    print(f'Failed to import: {failed}')
    sys.exit(1)
else:
    print('All key packages verified successfully')
"
RESULT=$?
if [[ ${RESULT} == "${TRUE}" ]]; then
	print_success "All key packages verified"
else
	print_error "Some packages failed verification"
	exit 1
fi

# Create necessary directories
print_status "Creating project directories..."
mkdir -p logs data/training data/testing data/samples images

# Set up environment variables
print_status "Setting up environment variables..."
cat >.env <<EOF
# Juniper Canopy Environment Variables
CASCOR_ENV=development
CASCOR_DEBUG=true
CASCOR_LOG_LEVEL=DEBUG
CASCOR_CONSOLE_LOG_LEVEL=INFO
CASCOR_FILE_LOG_LEVEL=DEBUG
CASCOR_CONFIG_PATH=conf/app_config.yaml

# Performance settings
OMP_NUM_THREADS=4
MKL_NUM_THREADS=4
NUMBA_NUM_THREADS=4

# Application settings
CASCOR_HOST=127.0.0.1
CASCOR_PORT=8050
EOF

print_success "Environment file created"

# Create a simple test script
print_status "Creating test script..."
cat >test_setup.py <<'EOF'
#!/usr/bin/env python3
"""
Simple test script to verify Juniper Canopy setup
"""

import sys
import os
from datetime import datetime

def test_imports():
    """Test that all required packages can be imported."""
    print("Testing package imports...")
    packages = [
        'dash', 'fastapi', 'plotly', 'redis', 'torch',
        'numpy', 'pandas', 'yaml', 'colorama', 'psutil'
    ]

    for package in packages:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError as e:
            print(f"  ✗ {package}: {e}")
            return False

    return True

def test_logging():
    """Test the logging framework."""
    print("\nTesting logging framework...")
    try:
        sys.path.append('src')
        from logging.logger import get_system_logger, get_training_logger

        system_logger = get_system_logger()
        training_logger = get_training_logger()

        system_logger.info("System logger test message")
        training_logger.info("Training logger test message")

        print("  ✓ Logging framework functional")
        return True
    except Exception as e:
        print(f"  ✗ Logging framework error: {e}")
        return False

def test_directories():
    """Test that required directories exist."""
    print("\nTesting directory structure...")
    required_dirs = [
        'conf', 'notes', 'src', 'data', 'logs', 'images', 'utils'
    ]

    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            print(f"  ✓ {dir_name}/")
        else:
            print(f"  ✗ {dir_name}/ (missing)")
            return False

    return True

def main():
    print("=" * 50)
    print("Juniper Canopy Setup Verification")
    print("=" * 50)
    print(f"Python version: {sys.version}")
    print(f"Test time: {datetime.now()}")
    print()

    tests = [
        ("Package imports", test_imports),
        ("Directory structure", test_directories),
        ("Logging framework", test_logging),
    ]

    passed = 0
    for test_name, test_func in tests:
        if test_func():
            passed += 1

    print("\n" + "=" * 50)
    print(f"Tests passed: {passed}/{len(tests)}")

    if passed == len(tests):
        print("🎉 Setup verification completed successfully!")
        print("\nNext steps:")
        print("1. Activate environment: conda activate JuniperPython")
        print("2. Start development: python -m src.main")
    else:
        print("❌ Some tests failed. Please check the setup.")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF

# Make test script executable
chmod +x test_setup.py

# Run the test script
print_status "Running setup verification..."
python test_setup.py
RESULT=$?

if [[ ${RESULT} == "${TRUE}" ]]; then
	print_success "Setup verification completed successfully!"
else
	print_error "Setup verification failed"
	exit 1
fi

# Final instructions
print_status "Setup completed successfully!"
echo
echo "To start working with the Juniper Canopy:"
echo "1. Activate the environment: conda activate ${ENV_NAME}"
echo "2. Navigate to project directory: cd ${PROJECT_DIR}"
echo "3. Start development server: python -m src.main"
echo
echo "Configuration files are available in the conf/ directory"
echo "Documentation is available in the notes/ directory"
echo "Logs will be written to the logs/ directory"
echo
print_success "Happy coding! 🚀"
