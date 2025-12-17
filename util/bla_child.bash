#!/usr/bin/env bash

TRUE="0"
FALSE="1"


# Get child script info
CHILD_PID="$$"
CHILD_BASH_PID="${BASHPID}"

CHILD_PATH="$(realpath "${BASH_SOURCE[0]}")"
CHILD_BASH_SOURCE="$(echo "${BASH_SOURCE[@]}")"


# Display child script info
echo -ne "\nChild: Child Script: \n"
echo -ne "\t${CHILD_PATH}\n"

echo -ne "Child: Child Bash Source: \n"
echo -ne "\t${CHILD_BASH_SOURCE}\n"

echo "Child: Child PID:      ${CHILD_PID}"
echo "Child: Child Bash Pid: ${CHILD_BASH_PID}"


# Get parent script info
PARENT_PID="${PPID}"

PARENT_CMD="$(cat /proc/${PARENT_PID}/cmdline)"

PARENT="$(ps -o args= ${PARENT_PID})"


# Display parent script info
echo "Child: Parent Pid:     ${PARENT_PID}"
echo "\"${PPID}\""

echo "Child: Parent Cmd:     ${PARENT_CMD}"
cat /proc/${PARENT_PID}/cmdline

echo "Child: Parent:         ${PARENT}"
ps -o args= ${PARENT_PID}
