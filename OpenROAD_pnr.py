from openroad import Tech, Design, Timing
import pdn, odb, utl
import openroad as ord
from pathlib import Path
import os, argparse, shutil, re
    
    
def repair_timing(design):
    design.evalTclString("repair_timing")
    return design

def repair_design(design):
    design.evalTclString("estimate_parasitics") 
    design.evalTclString("repair_design")
    return design

def config_gnc(design):
    for net in design.getBlock().getNets():
        if net.getSigType() == "POWER" or net.getSigType() == "GROUND":
            net.setSpecial()

    VDD_net = design.getBlock().findNet("VDD")
    VSS_net = design.getBlock().findNet("VSS")

    # Create VDD/VSS nets if they don't exist
    if VDD_net == None:
        VDD_net = odb.dbNet_create(design.getBlock(), "VDD")
        VDD_net.setSpecial()
        VDD_net.setSigType("POWER")
        odb.dbBTerm_create(VDD_net , 'VDD')

    if VSS_net == None:
        VSS_net = odb.dbNet_create(design.getBlock(), "VSS")
        VSS_net.setSpecial()
        VSS_net.setSigType("GROUND")
        odb.dbBTerm_create(VSS_net , 'VSS')
    
    # Connect power pins to global nets
    design.getBlock().addGlobalConnect(region = None,
        instPattern = ".*", 
        pinPattern = "^VDD$",
        net = VDD_net, 
        do_connect = True)
    design.getBlock().addGlobalConnect(region = None,
        instPattern = ".*",
        pinPattern = "^VDDPE$",
        net = VDD_net,
        do_connect = True)
    design.getBlock().addGlobalConnect(region = None,
        instPattern = ".*",
        pinPattern = "^VDDCE$",
        net = VDD_net,
        do_connect = True)
    design.getBlock().addGlobalConnect(region = None,
        instPattern = ".*",
        pinPattern = "^VSS$",
        net = VSS_net, 
        do_connect = True)
    design.getBlock().addGlobalConnect(region = None,
        instPattern = ".*",
        pinPattern = "^VSSE$",
        net = VSS_net,
        do_connect = True)
    design.getBlock().globalConnect()

def run_flow(design_name):
    # This is the flow to run placement and global routing using OpenROAD.
    # The same flow will be used during evaluation phase.
    # Initialize OpenROAD objects and read technology files
    tech = Tech()
    # Set paths to library and design files
    libDir = Path("../platform/ASAP7/lib/")
    lefDir = Path("../platform/ASAP7/lef/")

    designDir = Path("../designs/%s/EDA_files/"%design_name)

    fp_sdc = Path("../designs/%s/EDA_files/"%design_name)
    # Read all liberty (.lib) and LEF files from the library directories
    libFiles = libDir.glob("*.lib")
    techLefFiles = lefDir.glob("*tech*.lef")
    lefFiles = lefDir.glob('*.lef')
    
    # Load liberty timing libraries
    for libFile in libFiles:
        tech.readLiberty(libFile.as_posix())
    
    # Load technology and cell LEF files  
    for techLefFile in techLefFiles:
        tech.readLef(techLefFile.as_posix())
    
    for lefFile in lefFiles:
        tech.readLef(lefFile.as_posix())
    
    design = Design(tech)

    # Read netlist
    verilogFile = "%s/%s.v"%(designDir.as_posix(), design_name)

    design.readVerilog(verilogFile)
    design.link(design_name)
    
    # Config Global Net Connect
    config_gnc(design)

    # Read floorplan def file
    defFile = "%s/%s_fp.def.gz"%(fp_sdc.as_posix(), design_name)
    design.evalTclString("read_def -floorplan_initialize "+defFile)
    #design.readDef(defFile)
   
    # Read the SDC file
    sdcFile = "%s/%s.sdc"%(fp_sdc.as_posix(), design_name)
    design.evalTclString("read_sdc %s"%sdcFile)
    design.evalTclString("source ../platform/ASAP7/setRC.tcl")

    # Configure and run global placement
##########################################################################################################################
##########################################################################################################################
    print("###run global placement###")
    design.evalTclString("global_placement -routability_driven -init_density_penalty 0.05 -initial_place_max_iter 10")
    
    # Run initial detailed placement
    site = design.getBlock().getRows()[0].getSite()
    max_disp_x = int((design.getBlock().getBBox().xMax() - design.getBlock().getBBox().xMin()) / site.getWidth())
    max_disp_y = int((design.getBlock().getBBox().yMax() - design.getBlock().getBBox().yMin()) / site.getHeight())
    print("###run legalization###")
    design.getOpendp().detailedPlacement(max_disp_x, max_disp_y, "")
##########################################################################################################################
##########################################################################################################################
    if design_name not in ["ac97_top","aes_cipher_top"]:
        design = repair_design(design)
    # Run Global Routing and Estimate Global Routing RC
    signal_low_layer = design.getTech().getDB().getTech().findLayer("M1").getRoutingLevel()
    signal_high_layer = design.getTech().getDB().getTech().findLayer("M8").getRoutingLevel()
    clk_low_layer = design.getTech().getDB().getTech().findLayer("M1").getRoutingLevel()
    clk_high_layer = design.getTech().getDB().getTech().findLayer("M8").getRoutingLevel()
    grt = design.getGlobalRouter()
    grt.clear()
    grt.setAllowCongestion(True)
    grt.setMinRoutingLayer(signal_low_layer)
    grt.setMaxRoutingLayer(signal_high_layer)
    grt.setMinLayerForClock(clk_low_layer)
    grt.setMaxLayerForClock(clk_high_layer)
    grt.setAdjustment(0.5)
    grt.setVerbose(True)
    print("###run global routing###")
    grt.globalRoute(False)
    ##########################################
    design.evalTclString("set_routing_layers -signal M1-M8 -clock M1-M8")
    design.evalTclString("set_global_routing_layer_adjustment * 0.5")
    design.evalTclString("global_route -allow_congestion")
    design.evalTclString("estimate_parasitics -global_routing")
    ###########################################
    if design_name not in ["ac97_top"]:
        design = repair_timing(design)
    # # fileDir = "./"    

    outDir = "./results
    os.makedirs(outDir, exist_ok=True)
    
    # Write final Verilog file
    design.evalTclString(f"write_verilog ./results/{design_name}_resynth.v")
