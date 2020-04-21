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
parser.add_argument("--old_miraclegrue_config_file", action='store', nargs=1, required=False, help="The miraclegrue config file.  This may be either a plain old .json file, or an hjson file, which is json with more relaxed syntax, and allows comments.")
parser.add_argument("--old_miraclegrue_config_schema_file", action='store', nargs=1, required=False, help="The miraclegrue config schema file of the old version of miracle_grue (to be compared against the schema of the current version of miracle_grue")
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

miraclegrueConfig = hjson.load(open(miraclegrue_config_file_path ,'r'))

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

def makeBlockComment(x):
    lines = str(x).splitlines()  
    return "\n".join(
        ["/* " + lines[0]]
        + list(
            map(
                lambda y: " * " + y,
                lines[1:]
            )
        )
        + [" */"]
    )

def addParentheticalRemarkAtEndOfFirstLine(x, remark=None): 
    lines = str(x).splitlines()
    return "\n".join(
        [lines[0] + (" (" + str(remark) + ")" if remark else "")]
        + lines[1:]
    )


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
    # print("getSchemedType() was called with path " + str(path))
    schemedTypeName = getSchemedTypeName(path, schema)
    if schemedTypeName:
        return schema.get(schemedTypeName)
    return None

def getMemberIds(schemedType):
    return (
        map(
            lambda x: x['id'],
            schemedType['members']
        )
        if (schemedType and schemedType.get('mode') == "aggregate" )
        else None
    )


#returns the annotation text that is to appear immediately
# before the entry having the specified path.
def getAnnotationForEntry(path, schema):
    schemedTypeOfParent = getSchemedType(path[:-1],schema)
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
            return "\n".join(
                [path[-1]]
                + (["name: " + memberSpec.get('name')] if (memberSpec.get('name') and (memberSpec.get('name') != path[-1])) else [])
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
        else:
            return "THIS ELEMENT IS NOT SPECIFIED IN THE SCHEMA."
    else:
        return None

#entryFormat shall be a streing that is either "dictEntry" or "listEntry"
# def dumpsAnnotatedHjsonEntry(value, path, schema, entryFormat):
#     # print("dumpsAnnotatedHjsonEntry was called with path: " + str(path))
#     entry = (str(path[-1]) + ": "  if entryFormat == "dictEntry" else "") + dumpsAnnotatedHjsonValue(value, path, schema)
#     annotation = getAnnotationForEntry(path, schema)
#     return ("\n" + prefixAllLines(annotation, "// ") + "\n" if annotation else "") + entry


def dumpsAnnotatedHjsonValue(value, path, schema):
    # print("now working on path: " + str(path))
    returnValue=""
    schemedType = getSchemedType(path, schema)
    oldSchemedType = getSchemedType(path, oldSchema)
    
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
            keysInValue=set(value.keys())
            keysInSchema=set(getMemberIds(schemedType) or [])
            keysInOldSchema=set(getMemberIds(oldSchemedType) or [])
            subentryFormat="dictEntry"
        else:
            braces=["[","]"]
            keysInValue=set(range(len(value)))
            keysInSchema=set([])
            keysInOldSchema=set([])
            subentryFormat="listEntry"
        returnValue += braces[0] + "\n"
        for key in sorted(list(keysInValue.union(keysInSchema))):
            annotation = None
            if key in keysInOldSchema and key not in keysInSchema:
                annotation = addParentheticalRemarkAtEndOfFirstLine(
                    getAnnotationForEntry(path + [key], oldSchema),
                    "DELETED FROM SCHEMA, BUT YOU HAVE STILL SPECIFIED A VALUE"
                )



            else:
                annotation = getAnnotationForEntry(path + [key], schema)
                if annotation and (key in keysInSchema) and (key not in keysInOldSchema):
                    annotation = addParentheticalRemarkAtEndOfFirstLine(
                        annotation,
                        "NEW IN SCHEMA"
                    )
            
            oldSubValue = (
                oldMiraclegrueConfig.get(key)
                if len(path) == 0 else None
            )

            if key in keysInValue:
                subValue = value[key]
                entry = (key + ": "  if subentryFormat == "dictEntry" else "") + dumpsAnnotatedHjsonValue(subValue, path + [key], schema)
            else:
                subValue = None
                entry = "// VALUE NOT SPECIFIED"
            
            returnValue += indentAllLines(
                (
                    "\n" + makeBlockComment(annotation) + "\n" 
                    if annotation else ""
                ) 
                + entry
                + (
                    prefixAllLines(
                        (
                            "same as value in old config"
                            if (subValue!=None and (hjson.loads(hjson.dumps(subValue)) == hjson.loads(hjson.dumps(oldSubValue))))
                            else "value in old config: " + hjson.dumps(oldSubValue)
                        ), 
                        "// "
                    )
                    if oldSubValue != None else ""
                )
            ) + "\n"
        for key in sorted(list(keysInOldSchema.difference(keysInSchema))):
            annotation = addParentheticalRemarkAtEndOfFirstLine(
                getAnnotationForEntry(path + [key], oldSchema),
                "DELETED FROM SCHEMA"
            )
            oldSubValue = (
                oldMiraclegrueConfig.get(key)
                if len(path) == 0 else None
            )
            returnValue += indentAllLines(
                (
                    "\n" + makeBlockComment(annotation) + "\n" 
                    if annotation else ""
                ) 
                + (
                    prefixAllLines("value in old config: " + hjson.dumps(oldSubValue), "// ")
                    if oldSubValue != None else ""
                )
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
    oldSchema = json.load(open(pathlib.Path(args.old_miraclegrue_config_schema_file[0]).resolve(),'r'))
    oldMiraclegrueConfig = json.load(open(pathlib.Path(args.old_miraclegrue_config_file[0]).resolve(),'r'))
    annotatedConfigFile = open(pathlib.Path(args.output_annotated_miraclegrue_config_file[0]).resolve() ,'w')
    annotatedConfigFile.write(
        dumpsAnnotatedHjsonValue(
            value=miraclegrueConfig,
            schema=schema,
            path=[]
        )
    )

    annotatedConfigFile.close()
    pass


temporary_miraclegrue_config_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
json.dump(miraclegrueConfig, temporary_miraclegrue_config_file, sort_keys=True, indent=4)
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
    "--machine_id=" + miraclegrueConfig['_bot'] + "",
    "--extruder_ids=" + ",".join(miraclegrueConfig['_extruders']) + "",
    "--material_ids=" + ",".join(miraclegrueConfig['_materials']) + "",
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




