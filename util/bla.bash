#!/usr/bin/env bash

TRUE="0"
FALSE="1"

CHILD_SCRIPT="./bla_child.bash"

PARENT_PATH="$(realpath "${BASH_SOURCE[0]}")"
PATENT_BASH_SOURCE="$(echo "${BASH_SOURCE[@]}")"


echo -ne "\nParent: Parent Script Path: \n"
echo -ne "\t\"${PARENT_PATH}\"\n\n"

echo -ne "Parent: Parent Bash Source: \n"
echo -ne "\t\"${PARENT_BASH_SOURCE}\"\n"

echo -ne "Parent: Running Child script: \"${CHILD_SCRIPT}\":\n"
${CHILD_SCRIPT}
SUCCESS="$?"

echo "Parent: ${CHILD_SCRIPT} returned $( [[ "${SUCCESS}" == "${TRUE}" ]] && echo "Successfully:" || echo "Failure:" ) (\$?: ${SUCCESS})"
