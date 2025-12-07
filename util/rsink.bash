#!/usr/bin/env bash

if [[ $1 ]]; then

dest="./dest"
src="./source"

test $2 && dest="$2"
test $1 && src="$1"

rsync -a --safe-links ${src}/ ${dest}/

abs_src="$(realpath -- ${src})"
for i in $(find ${src} -type l); do
  target="$(target="$(readlink -f -- $i)" && echo "${target%/*}")"
  while [[ $target && ( ! $abs_src -ef $target ) ]]; do target="${target%/*}"; done
  test ! ${target} && rsync -aL ${i} ${i/$src/$dest}
done
