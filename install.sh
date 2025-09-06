#!/usr/bin/bash

OPENLANE_DIR=/eda/asic/OpenLane
OPEN_PDKS_DIR=/eda/asic/open_pdks
PDK_ROOT=/eda/asic/.ciel

sudo apt update
sudo apt install -y build-essential python3 python3-pip make git gcc ruby ruby-dev \
    python3-dev libexpat1-dev libssl-dev apt-transport-https ca-certificates curl \
    software-properties-common docker docker-compose magic

sudo usermod -aG docker $USER
mkdir -p $PDK_ROOT
mkdir -p $OPEN_PDKS_DIR
mkdir -p $OPENLANE_DIR
git clone https://github.com/The-OpenROAD-Project/OpenLane $OPENLANE_DIR
cd $OPENLANE_DIR
sudo systemctl restart docker
make

git clone https://github.com/RTimothyEdwards/open_pdks $OPEN_PDKS_DIR
cd $OPEN_PDKS_DIR

./configure --prefix=$PDK_ROOT
mkdir -p $PDK_ROOT/share
make install