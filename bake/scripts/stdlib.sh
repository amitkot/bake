#!/usr/bin/env bash

if [ "$(uname)" == Darwin ]; then
    bake-sed() { command sed -l "$@"; }
else
    bake-sed() { command sed -u "$@"; }
fi

# Syntax sugar.
bake-indent() {
    bake-sed "s/^/   /"
}

# ---------------------
# From: https://github.com/heroku/buildpack-stdlib/blob/master/stdlib.sh

# Buildpack Steps.
bake-step() {
    if [[ "$*" == "-" ]]; then
        read -r output
    else
        output=$*
    fi
    echo -e "\\e[1m\\e[36m=== $output\\e[0m"
    unset output
}

# Buildpack Error.
bake-error() {
    if [[ "$*" == "-" ]]; then
        read -r output
    else
        output=$*
    fi
    echo -e "\\e[1m\\e[31m=!= $output\\e[0m"
}

# Buildpack Warning.
bake-warn() {
    if [[ "$*" == "-" ]]; then
        read -r output
    else
        output=$*
    fi
    echo -e "\\e[1m\\e[33m=!= $output\\e[0m"
}