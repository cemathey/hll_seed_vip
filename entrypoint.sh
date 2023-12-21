#!/usr/bin/env bash
set -e
set -x

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