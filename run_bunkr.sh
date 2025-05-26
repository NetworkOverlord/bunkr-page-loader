#!/bin/bash
docker build -t bunkr-loader .
docker run --rm -v $HOME/bunkr_logs:/root/bunkr_logs bunkr-loader "$@"
