#!/usr/bin/env bash
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
# File Name:     setup_environment.bash
# File Path:     <Project>/<Sub-Project>/<Application>/util/
#
# Date:          2025-10-11
# Last Modified: 2026-01-04
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#    This script sets up the development environment for the Juniper Canopy application.
#
#####################################################################################################################################################################################################
# Notes:
#     Juniper Canopy Environment Setup Script
#     This script sets up the development environment for the Juniper Canopy application
#
########################################################################################################)#############################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################


#####################################################################################################################################################################################################
# Source script config file
#####################################################################################################################################################################################################
set -o functrace
# shellcheck disable=SC2155
export PARENT_PATH_PARAM="$(realpath "${BASH_SOURCE[0]}")" && INIT_CONF="$(dirname "$(dirname "${PARENT_PATH_PARAM}")")/conf/init.conf"
# shellcheck disable=SC2015,SC1090
[[ -f "${INIT_CONF}" ]] && source "${INIT_CONF}" || { echo "Init Config File Not Found. Unable to Continue."; exit 1; }


#####################################################################################################################################################################################################
# Define Function to check if command exists
#####################################################################################################################################################################################################
function command_exists() {
    # shellcheck disable=SC2015
    [[ ${DEBUG} == "${TRUE}" ]] && command -v "$1" || command -v "$1" >/dev/null 2>&1   # trunk-ignore(shellcheck/SC2015)
}


#####################################################################################################################################################################################################
# Define Command and Offset based on package manager choice
#####################################################################################################################################################################################################
log_trace "Define Command and Offset based on package manager choice"
if [[ "${USE_CONDA}" == "${TRUE}" ]]; then
	CMD="${CONDA_CMD}"
	OFFSET="${CONDA_OFFSET}"
elif [[ "${USE_MAMBA}" == "${TRUE}" ]]; then
	CMD="${MAMBA_CMD}"
	OFFSET="${MAMBA_OFFSET}"
else
    log_fatal "No package manager selected. Unable to continue."
fi

log_debug "OS Type: ${OS_TYPE}"
if [[ "${OS_TYPE}" == "${LINUX}" ]]; then
	BASH_CONFIG="/home/pcalnon/.bashrc"
    log_debug "Bash Linux config file: ${BASH_CONFIG}"
elif [[ "${OS_TYPE}" == "${MACOS}" ]]; then
	BASH_CONFIG="/Users/pcalnon/.bash_profile"
    log_debug "Bash MacOS config file: ${BASH_CONFIG}"
else
    log_fatal "Unsupported OS: ${OS_TYPE}"
fi

log_debug "Bash config file: ${BASH_CONFIG}"
log_info "Starting ${PROJECT_NAME} environment setup..."


#####################################################################################################################################################################################################
# Check if conda is installed
#####################################################################################################################################################################################################
log_trace "Check if conda is installed"
RESULT="$(command_exists conda)"
log_debug "Conda check result: ${RESULT}"
if [[ "${RESULT}" == "" ]]; then
	log_info "Please install Miniconda or Anaconda and try again"
	log_fatal "Conda is not installed or not in PATH"
fi
log_debug "Verified Conda is installed"

CONDA_VERSION="$(conda --version)"
log_info "Conda found: ${CONDA_VERSION}"


# TODO: Done above here


#####################################################################################################################################################################################################
# Check if mamba is installed
#####################################################################################################################################################################################################
log_trace "Check if mamba is installed"
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


#####################################################################################################################################################################################################
# Navigate to project directory
#####################################################################################################################################################################################################
log_trace "Navigate to project directory"
cd "${PROJECT_DIR}" || {
	print_error "Failed to navigate to project directory: ${PROJECT_DIR}"
	exit 1
}
[[ ${DEBUG} == "${TRUE}" ]] && print_status "DEBUG: Navigated to project directory"
WORKING_DIR="$(pwd || 0)"
print_status "Working in directory: ${WORKING_DIR}"


#####################################################################################################################################################################################################
# Check if environment already exists
#####################################################################################################################################################################################################
log_trace "Check if conda environment already exists"
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


#####################################################################################################################################################################################################
# Creating conda environment from Create conda environment YAML file
#####################################################################################################################################################################################################
log_trace "Creating conda environment from Create conda environment YAML file"
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
	# shellcheck disable=SC1090
	source "${BASH_CONFIG}"    # trunk-ignore(shellcheck/SC1090)
else
	print_warning "Bash config not found: ${BASH_CONFIG}"
fi


#####################################################################################################################################################################################################
# Try to activate the environment; ensure conda is available in this shell
#####################################################################################################################################################################################################
log_trace "Try to activate the environment; ensure conda is available in this shell"
if command -v conda >/dev/null 2>&1; then
	conda activate "${ENV_NAME}"
else
	print_error "Conda not found in PATH during activation"
	exit 1
fi


#####################################################################################################################################################################################################
# Verify activation
#####################################################################################################################################################################################################
log_trace "Verify activation"
if [[ ${CONDA_DEFAULT_ENV} != "${ENV_NAME}" ]]; then
	print_error "Failed to activate environment"
	exit 1
fi

print_success "Environment '${ENV_NAME}' activated"


#####################################################################################################################################################################################################
# Install additional pip packages if needed
#####################################################################################################################################################################################################
log_trace "Install additional pip packages"
print_status "Installing additional pip packages..."
pip install -r conf/requirements.txt


#####################################################################################################################################################################################################
# Verify key packages
#####################################################################################################################################################################################################
log_trace "Verify key packages"
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


#####################################################################################################################################################################################################
# Create necessary directories
#####################################################################################################################################################################################################
log_trace "Create necessary directories"
print_status "Creating project directories..."
mkdir -p logs data/training data/testing data/samples images


#####################################################################################################################################################################################################
# Set up environment variables
#####################################################################################################################################################################################################
log_trace "Set up environment variables"
echo "${ENV_DOT_FILE_CONTENT}" >"${ENV_DOT_FILE}"
log_info "Environment file created"


#####################################################################################################################################################################################################
# Create a simple test script
#####################################################################################################################################################################################################
log_trace "Creating test script..."
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


#####################################################################################################################################################################################################
# Make test script executable
#####################################################################################################################################################################################################
log_trace "Make test script executable"
log_debug "chmod +x test_setup.py"
chmod +x test_setup.py


#####################################################################################################################################################################################################
# Run the test script
#####################################################################################################################################################################################################
log_trace "Running setup verification..."
log_debug "python test_setup.py"
python test_setup.py; SUCCESS=$?

# shellcheck disable=SC2015
[[ "${SUCCESS}" != "${TRUE}" ]] && log_critical "Test Environment's Setup verification failed" || log_info "Setup verification completed successfully!"


#####################################################################################################################################################################################################
# Final instructions
#####################################################################################################################################################################################################
log_info "Setup completed successfully!"

echo "Setup completed successfully!"
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
echo "Happy coding! 🚀"

log_info "Happy coding! 🚀"
exit $(( TRUE ))
