from OpenROAD_pnr import *
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Example script to perform timing optimization techniques using OpenROAD.")
    parser.add_argument("-d", default="ac97_top", help="Give the design name")
    args = parser.parse_args() 
    
    run_flow(args.d)

