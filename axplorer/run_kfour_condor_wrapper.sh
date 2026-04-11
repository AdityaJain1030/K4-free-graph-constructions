#!/usr/bin/env bash
# HTCondor wrapper — executed on the compute node.
# Compute nodes may start in an arbitrary scratch directory;
# cd $HOME first to get a known starting point before entering the project.
cd "$HOME"
exec k4free/axplorer/run_kfour_production.sh "$@"
