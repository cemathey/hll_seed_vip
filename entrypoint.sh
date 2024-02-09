#!/usr/bin/env bash
set -e
set -x

export TAG_VERSION=$(cat /code/tag_version)

if [ ! -d "./config" ]
then
    echo "Creating config directory"
    mkdir ./config
fi

if [ ! -d "./logs" ]
then
    echo "Creating logs directory"
    mkdir ./logs
fi


PYTHONPATH=. poetry run python /code/hll_seed_vip/cli.py
