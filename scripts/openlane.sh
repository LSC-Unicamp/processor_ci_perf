#!/usr/bin/bash

DOCKER_IMAGE=ghcr.io/the-openroad-project/openlane:413d301090a476f8d34cf24dc2447da17dfab187-amd64
OPENLANE_DIR=/eda/asic/OpenLane
DESIGN_DIR=/eda/processor_ci_perf/blink2
PDK_ROOT=/home/$(whoami)/.ciel
PDK=sky130A

HOME=/home/$(whoami)

docker run --rm -it \
  -v $OPENLANE_DIR:/openlane \
  -v $DESIGN_DIR:/openlane/designs/blink2 \
  -v $HOME:$HOME \
  -v $HOME/.ciel:$HOME/.ciel \
  -e PDK_ROOT=$PDK_ROOT \
  -e PDK=$PDK \
  $DOCKER_IMAGE \
  sh -c "./flow.tcl -design blink2"
