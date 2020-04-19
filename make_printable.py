import argparse
import os
import re
import json
import pathlib
import sys
import math
# import numpy
import subprocess



parser = argparse.ArgumentParser(description="Generate a .makerbot toolpath file from a .thing file and a mircale_grue configuration file.")
parser.add_argument("--input_file", action='store', nargs=1, required=True, help="the .thing file to be sliced.")
parser.add_argument("--output_file", action='store', nargs=1, required=True, help="the .makerbot file to be created.")
parser.add_argument("--makerware_path", action='store', nargs=1, required=True, help="the path of the MakerWare folder, which comes with Makerbot Print.")
parser.add_argument("--miraclegrue_config_file", action='store', nargs=1, required=False, default="0", help="The miraclegrue config file.  This may be either a plain old .json file, or an hjson file, which is json with more relaxed syntax, and allows comments.")


args = parser.parse_args()

#resolve all of the paths passed as arguments to fully qualified paths:
input_file_path = pathlib.Path(args.input_file[0]).resolve()
output_file_path = pathlib.Path(args.output_file[0]).resolve()
makerware_path = pathlib.Path(args.makerware_path[0]).resolve()
miraclegrue_config_file_path = pathlib.Path(args.miraclegrue_config_file[0]).resolve()

#the path of the python executable included with makerware:
makerware_python_executable_path = makerware_path.joinpath("python3.4.exe").resolve()
makerware_python_working_directory_path = makerware_path.joinpath("python34").resolve()


#the path of the makerware sliceconfig python script:
makerware_sliceconfig_path = makerware_path.joinpath("sliceconfig").resolve()

miraclegrue_config = json.load(open(miraclegrue_config_file_path ,'r'))

args = [
    str(makerware_python_executable_path),
    str(makerware_sliceconfig_path),
    "--status-updates",
    "--input=" + str(input_file_path) +  "",
    "--output=" + str(output_file_path) +  "",
    "--machine_id=" + miraclegrue_config['_bot'] + "",
    "--extruder_ids=" + ",".join(miraclegrue_config['_extruders']) + "",
    "--material_ids=" + ",".join(miraclegrue_config['_materials']) + "",
    "--profile=" + str(miraclegrue_config_file_path) + "" ,
    "slice"
]

completedProcess = subprocess.run(
    cwd=makerware_python_working_directory_path,
    args=args,
    capture_output = True,
    text=True
)
print("\n")
print("completedProcess.args: " + str(completedProcess.args))
print("\n")
print("completedProcess.stdout: " + str(completedProcess.stdout))
print("\n")
print("completedProcess.stderr: " + str(completedProcess.stderr))
print("\n")
print("completedProcess.returncode: " + str(completedProcess.returncode))
print("\n")
# print("completedProcess.stderr: " + json.dumps(json.loads(str(completedProcess.stderr))) )




# if completedProcess.returncode != 0 or not os.path.isfile(cookieJarFilePath):
#     print("the call to curl seems to have failed.")
#     print(str(completedProcess))
#     exit



