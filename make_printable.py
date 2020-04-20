import argparse
import os
import re
import json
import pathlib
import sys
import math
# import numpy
import subprocess
import hjson
import tempfile



parser = argparse.ArgumentParser(description="Generate a .makerbot toolpath file from a .thing file and a mircale_grue configuration file.")
parser.add_argument("--input_file", action='store', nargs=1, required=True, help="the .thing file to be sliced.")
parser.add_argument("--output_file", action='store', nargs=1, required=True, help="the .makerbot file to be created.")
parser.add_argument("--makerware_path", action='store', nargs=1, required=True, help="the path of the MakerWare folder, which comes with Makerbot Print.")
parser.add_argument("--miraclegrue_config_file", action='store', nargs=1, required=True, help="The miraclegrue config file.  This may be either a plain old .json file, or an hjson file, which is json with more relaxed syntax, and allows comments.")
# parser.add_argument("--miraclegrue_config_schema_file", action='store', nargs=1, required=False, help="The miraclegrue config schema file.")
parser.add_argument("--output_annotated_miraclegrue_config_file", action='store', nargs=1, required=False, help="An hjson file to be created by inserting the descriptions from the schema, as comments, interspersed within the miracle_grue_config json entries.")





args, unknownArgs = parser.parse_known_args()

#resolve all of the paths passed as arguments to fully qualified paths:
input_file_path = pathlib.Path(args.input_file[0]).resolve()
output_file_path = pathlib.Path(args.output_file[0]).resolve()
makerware_path = pathlib.Path(args.makerware_path[0]).resolve()
miraclegrue_config_file_path = pathlib.Path(args.miraclegrue_config_file[0]).resolve()



#the path of the python executable included with makerware:
makerware_python_executable_path = makerware_path.joinpath("python3.4.exe").resolve()
makerware_python_working_directory_path = makerware_path.joinpath("python34").resolve()
miracle_grue_executable_path = makerware_path.joinpath("miracle_grue.exe").resolve()

miraclegrue_config = hjson.load(open(miraclegrue_config_file_path ,'r'))

def tabbedWrite(file, content, tabLevel=0, tabString="    ", linePrefix=""):
    file.write(
        "\n".join(
            map( 
                lambda y: tabString*tabLevel + linePrefix + y,
                str(content).splitlines()
            )
        ) + "\n"
    )

def prefixAllLines(x, prefix):
    return "\n".join(
        map( 
            lambda y: prefix + y,
            str(x).splitlines()
        )
    )

def indentAllLines(x, indentString="    "):
    return prefixAllLines(x, indentString)

# path is expected to be a list (of keys)
def getSchemedTypeName(path, schema):
    if len(path) == 0:
        return '__top__'
    schemedTypeOfParent = getSchemedType(path[:-1],schema)
    if schemedTypeOfParent:
        if schemedTypeOfParent['mode'] == "aggregate":
            memberSpec = (
                    list(
                        filter(
                            lambda x: x['id'] == path[-1],
                            schemedTypeOfParent["members"]
                        )
                    ) or [None]
                )[0]
            if memberSpec:
                return memberSpec['type']
        elif schemedTypeOfParent['json_type'] == "object":
            return schemedTypeOfParent['value_type']
        elif schemedTypeOfParent['json_type'] == "array":
            return schemedTypeOfParent['element_type']
    return None

def getSchemedType(path, schema):
    schemedTypeName = getSchemedTypeName(path, schema)
    if schemedTypeName:
        return schema.get(schemedTypeName)
    return None

#entryFormat shall be a streing that is either "dictEntry" or "listEntry"
def dumpsAnnotatedHjsonEntry(value, path, schema, entryFormat):
    # print("dumpsAnnotatedHjsonEntry was called with path: " + str(path))
    schemedTypeName = getSchemedTypeName(path, schema)
    schemedType = getSchemedType(path, schema)
    schemedTypeOfParent = getSchemedType(path[:-1],schema)
    annotation = None
    entry = (str(path[-1]) + ": "  if entryFormat == "dictEntry" else "") + dumpsAnnotatedHjsonValue(value, path, schema)
    
    if schemedTypeOfParent and schemedTypeOfParent['mode'] == "aggregate":
        memberSpec = (
                list(
                    filter(
                        lambda x: x['id'] == path[-1],
                        schemedTypeOfParent["members"]
                    )
                ) or [None]
            )[0]
        if memberSpec:
            annotation = "\n".join(
                [memberSpec.get('name') or memberSpec.get('id')]  
                + list(
                    map(
                        lambda k: k + ": " + hjson.dumps(memberSpec[k]),
                        filter(
                            lambda k: k not in ['id','name'],
                            memberSpec.keys()
                        )
                    )
                )   
            )
    return ("\n" + prefixAllLines(annotation, "// ") + "\n" if annotation else "") + entry


def dumpsAnnotatedHjsonValue(value, path, schema):
    # print("now working on path: " + str(path))
    returnValue=""
    schemedTypeName = getSchemedTypeName(path, schema)
    schemedType = getSchemedType(path, schema)
    isIterable = (
        isinstance(value, dict)
        or isinstance(value, list)
        or (schemedType and schemedType.get('mode') == "aggregate" )
        or (schemedType and schemedType.get('json_type') == "object") 
        or (schemedType and schemedType.get('json_type') == "array" )
    )
    if isIterable:
        if isinstance(value, dict):
            braces=["{","}"]
            keys=value.keys()
            subentryFormat="dictEntry"
        else:
            braces=["[","]"]
            keys=range(len(value))
            subentryFormat="listEntry"
        returnValue += braces[0] + "\n"
        for key in keys:
            returnValue += indentAllLines(
                dumpsAnnotatedHjsonEntry(value[key], path + [key], schema, subentryFormat)
            ) + "\n"
        returnValue += braces[1] + "\n"
    else:
        returnValue += hjson.dumps(value) + "\n"
    return returnValue    

# if args.miraclegrue_config_schema_file and args.output_annotated_miraclegrue_config_file:
if args.output_annotated_miraclegrue_config_file:
    # generate an annotated hjson version of the config file, by
    # adding the descriptions in the schema as comments.
    # schema = json.load(open(pathlib.Path(args.miraclegrue_config_schema_file[0]).resolve() ,'r'))
    completedProcess = subprocess.run(
        args=[
            str(miracle_grue_executable_path),
            "--config-schema"   
        ],
        capture_output = True,
        text=True
    )
    schema = json.loads(completedProcess.stdout)
    

    annotatedConfigFile = open(pathlib.Path(args.output_annotated_miraclegrue_config_file[0]).resolve() ,'w')
    annotatedConfigFile.write(
        dumpsAnnotatedHjsonValue(
            value=miraclegrue_config,
            schema=schema,
            path=[]
        )
    )

    # tabLevel=0
    # #at the moment, I am only going to bother doing this at the top level of the hierarchy
    # tabbedWrite(file=annotatedConfigFile, tabLevel=tabLevel, content="{")
    # tabLevel += 1 
    # # for key in sorted(miraclegrue_config.keys()):
    # for key in miraclegrue_config.keys():
    #     schemaEntry = (list(
    #         filter(
    #             lambda x: x['id'] == key,
    #             schema["__top__"]["members"]
    #         )
    #     ) or [None])[0]
    #     # print("type(schemaEntry): " + str(type(schemaEntry)))

    #     if schemaEntry:
    #         tabbedWrite(file=annotatedConfigFile, tabLevel=tabLevel, linePrefix="//", content=
    #             (schemaEntry.get('name') or schemaEntry.get('id')) + "\n" + 
    #             # hjson.dumps(schemaEntry, indent=4)
    #             "\n".join(
    #                 list(
    #                     map(
    #                         lambda k: k + ": " + hjson.dumps(schemaEntry[k]),
    #                         filter(
    #                             lambda k: k not in ['id','name'],
    #                             schemaEntry.keys()
    #                         )
    #                     )
    #                 ) + [str(type(miraclegrue_config[key]))]
    #             )
    #         )
    #     tabbedWrite(file=annotatedConfigFile, tabLevel=tabLevel, content=
    #         str(key) + ": " + hjson.dumps(miraclegrue_config[key], indent=4)
    #     )
    #     tabbedWrite(file=annotatedConfigFile, tabLevel=tabLevel, content="")
    #     pass

    # tabLevel -= 1 
    # tabbedWrite(file=annotatedConfigFile, tabLevel=tabLevel, content="}")
    annotatedConfigFile.close()
    pass


temporary_miraclegrue_config_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
json.dump(miraclegrue_config, temporary_miraclegrue_config_file, sort_keys=True, indent=4)
temporary_miraclegrue_config_file.close()

temporary_miraclegrue_config_file_path = pathlib.Path(temporary_miraclegrue_config_file.name).resolve()

#the path of the makerware sliceconfig python script:
makerware_sliceconfig_path = makerware_path.joinpath("sliceconfig").resolve()



subprocessArgs = [
    str(makerware_python_executable_path),
    str(makerware_sliceconfig_path),
    "--status-updates",
    "--input=" + str(input_file_path) +  "",
    "--output=" + str(output_file_path) +  "",
    "--machine_id=" + miraclegrue_config['_bot'] + "",
    "--extruder_ids=" + ",".join(miraclegrue_config['_extruders']) + "",
    "--material_ids=" + ",".join(miraclegrue_config['_materials']) + "",
    "--profile=" + str(temporary_miraclegrue_config_file_path) + "" ,
    "slice"
]

completedProcess = subprocess.run(
    cwd=makerware_python_working_directory_path,
    args=subprocessArgs,
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
print("temporary_miraclegrue_config_file_path: " + str(temporary_miraclegrue_config_file_path))
print("\n")
print("temporary_miraclegrue_config_file_path: " + str(temporary_miraclegrue_config_file_path))
print("\n")
print("temporary_miraclegrue_config_file_path: " + str(temporary_miraclegrue_config_file_path))
print("\n")

# print("completedProcess.stderr: " + json.dumps(json.loads(str(completedProcess.stderr))) )




