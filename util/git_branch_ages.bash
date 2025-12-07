#!/usr/bin/env bash


git fetch --prune

#for k in $(git branch | sed s/^..//); do echo -e $(git log --color=always -1 --pretty=format:"%Cgreen%ci %Cblue%cr%Creset" $k --)\\t"$k";done | sort
echo -ne "\nLocal Branches:\n"
git for-each-ref --sort='committerdate:iso8601' --color --format="%(color:green)%(committerdate:iso8601)|%(color:blue)%(committerdate:relative)|%(color:reset)%09%(refname)" refs/heads | awk -F "refs/heads/" '{print $1 $2;}' | column -s '|' -t

echo -ne "\nRemote Branches:\n"
git for-each-ref --sort='committerdate:iso8601' --color --format="%(color:green)%(committerdate:iso8601)|%(color:blue)%(committerdate:relative)|%(color:reset)%09%(refname)" refs/remotes | awk -F "refs/remotes/" '{print $1 $2;}' | column -s '|' -t
