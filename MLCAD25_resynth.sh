#!/bin/bash

design_name=$1
/app/MLCAD25-Contest-Scripts-Benchmarks/OpenROAD/build/src/openroad -python main.py -d "$design_name"
