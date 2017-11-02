#!/usr/bin/env python

"""Copyright (c) 2017, Annika Wierichs, RWTH Aachen University

All rights reserved.
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
   * Redistributions of source code must retain the above copyright
     notice, this list of conditions and the following disclaimer.
   * Redistributions in binary form must reproduce the above copyright
     notice, this list of conditions and the following disclaimer in the
     documentation and/or other materials provided with the distribution.
   * Neither the name of the University nor the names of its contributors
     may be used to endorse or promote products derived from this
     software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


This script expects a text file containing function prototypes as input
(SRC_PATH). It generates the following C code snippets for each individual given
function in the input file. Todo notes are inserted whereever more work is
required.

1. The definition of a struct that contains all parameters and the return value
of a given function.
Required in: ./kernel/ibv.c

  Example:
  typedef struct {
      // Parameters:
      struct ibv_mr * mr;
      int flags;
      struct ibv_pd * pd;
      // Return value:
      int ret;
  } __attribute__((packed)) uhyve_ibv_rereg_mr_t;

2. The definition of the kernel space function that sends a KVM exit IO to
uhyve.
Required in: ./kernel/ibv.c

  Example:
  int ibv_rereg_mr(struct ibv_mr * mr, int flags, struct ibv_pd * pd) {
      uhyve_ibv_rereg_mr_t uhyve_args;
      uhyve_args->mr = (struct ibv_mr *) virt_to_phys((size_t) mr);
      uhyve_args->flags = flags;
      uhyve_args->pd = (struct ibv_pd *) virt_to_phys((size_t) pd);

      uhyve_send(UHYVE_PORT_IBV_REREG_MR, (unsigned) virt_to_phys((size_t) &uhyve_args));

      return uhyve_args.ret;
  }

3. The switch-case that catches the KVM exit IO sent to uhyve by the kernel.
Required in: ./tool/uhyve.c

  Example:
  case UHYVE_PORT_IBV_REREG_MR: {
    unsigned data = *((unsigned*)((size_t)run+run->io.data_offset));
    uhyve_ibv_rereg_mr_t * args = (uhyve_ibv_rereg_mr_t *) (guest_mem + data);

    int host_ret = ibv_rereg_mr(guest_mem+(size_t)args->mr, flags, guest_mem+(size_t)args->pd);
    args->ret = host_ret;
    break;
  }

The script also generates an enum mapping all functions to KVM exit IO port
names and numbers.
Required in: ./tool/uhyve-ibv.h

  Example:
  typedef enum {
    UHYVE_PORT_IBV_WC_STATUS_STR = 0x510,
    UHYVE_PORT_IBV_RATE_TO_MULT = 0x511,
    UHYVE_PORT_MULT_TO_IBV_RATE = 0x512,
    // ...
  } uhyve_ibv_t;
"""


# Path of the input file containing function prototypes.
SRC_PATH = "function-prototypes-0.txt"

# Paths of the files that are generated by the script.
IBV_GEN_PATH = "GEN-kernel-ibv.c"
UHYVE_CASES_GEN_PATH = "GEN-tools-uhyve.c"
UHYVE_IBV_HEADER_GEN_PATH = "GEN-tools-uhyve-ibv-ports.h"
INCLUDE_STDDEF_GEN_PATH = "GEN-include-hermit-stddef.h"
UHYVE_IBV_HEADER_STRUCTS_GEN_PATH = "GEN-tools-uhyve-ibv-structs.h"
UHYVE_HOST_FCNS_GEN_PATH = "GEN-tools-uhyve-ibv.c"

# Starting number of the sequence used for IBV ports.
PORT_NUMBER_START = 0x510

TABS = ["", "\t", "\t\t", "\t\t\t", "\t\t\t\t"]
NEWLINES = ["", "\n", "\n\n"]


def get_struct_name(function_name):
  """Returns the matching struct name for a given function name.
  """
  return "uhyve_{0}_t".format(function_name)


def parse_line(line):
  """Parses a line containing a function prototype.

  Args:
    line: Line of the following format: 
          <return_type> <function_name>(<param_type> <param_name>, [...])

  Returns:
    Return type, function name, parameters as Tuple[string, string, list[string]]
  """
  parens_split = line.split("(")

  ret_and_name = parens_split[0].split(" ")
  all_params = parens_split[-1][:-1]

  ret = " ".join(ret_and_name[:-1])
  function_name = ret_and_name[-1]

  params = all_params.split(",")
  params[-1] = params[-1][:-1]

  return ret, function_name, params


def generate_struct(ret, function_name, params):
  """Generates the struct to hold a function's parameters and return value.

  Args:
    ret: Return type as string.
    function_name: Function name as string.
    params: Parameters as list of strings.

  Returns:
    Generated struct as string.
  """
  struct = "typedef struct {\n"
  if params:
    struct += "\t// Parameters:\n"
    for param in params:
      struct += "\t{0};\n".format(param)

  if ret is not "void":
    struct += "\t// Return value:\n"
    struct += "\t{0} ret;\n".format(ret)

  struct_name = get_struct_name(function_name)
  struct += "}} __attribute__((packed)) {0};\n\n".format(struct_name)

  return struct


def generate_kernel_function(ret, function_name, params):
  """Generates the kernel function that sends the KVM exit IO to uhyve.

  Args:
    ret: Return type as string.
    function_name: Function name as string.
    params: Parameters as list of strings.

  Returns:
    Generated function as string.
  """
  function = "{0} {1}({2}) {{\n".format(ret, function_name, ", ".join(params))

  # Create uhyve_args and define parameters
  struct_name = get_struct_name(function_name)
  function += "\t{0} uhyve_args;\n".format(struct_name)
  for param in params:
    param_split = param.split(" ")
    param_type = " ".join(param_split[:-1])
    param_name = param_split[-1]

    # Define struct members according to their type.
    if "**" in param_type:
      function += "\t// TODO: Take care of ** parameter.\n"
    elif "*" in param_type:
      function += "\tuhyve_args->{0} = " "({1}) virt_to_phys((size_t) {2});\n".format(
        param_name, param_type, param_name)
    else:
      function += "\tuhyve_args->{0} = {0};\n".format(param_name)

  # Allocate memory for return value if it is a pointer.
  if "**" in ret:
    function += "\n\t// TODO: Take care of return value.\n"
  elif "*" in ret:
    function += "\n\tuhyve_args->ret = kmalloc(sizeof({0}));\n".format(ret[:-2])

  # call uhyve_send() using the respective port ID.
  port_name = "UHYVE_PORT_" + function_name.upper()
  function += "\n\tuhyve_send({0}, (unsigned) virt_to_phys((size_t) " \
    "&uhyve_args));\n\n".format(port_name)

  function += "\t// TODO: Fix pointers in returned data structures.\n"

  function += "\treturn uhyve_args.ret;\n"
  function += "}\n\n\n"

  return function


def generate_uhyve_cases(function_names):
  """ Generates all switch-cases for uhyve's KVM exit IO.

  Args:
    function_names: All function names as a list of strings.

  Returns:
    Generated switch-cases as one single string.
  """
  cases = ""

  for function_name in function_names:
    port_name = "UHYVE_PORT_" + function_name.upper()
    struct_name = get_struct_name(function_name)

    cases += "{0}{1}case {2}:".format(NEWLINES[1], TABS[3], port_name)
    cases += "{0}{1}call_{2}(run, guest_mem);".format(NEWLINES[1], TABS[4], function_name)
    cases += "{0}{1}break;".format(NEWLINES[1], TABS[4])

  return cases


def generate_uhyve_host_function(ret, function_name, params):
  """Generates a switch-case that catches a KVM exit IO for the given function in uhyve.

  Args:
    ret: Return type as string.
    function_name: Function name as string.
    params: Parameters as list of strings.

  Returns:
    Generated switch-case code as string.
  """

  def generate_host_call_parameter(param):
    """Generates the parameter for the host's function called from within uhyve.

    This distinguishes between pointers and non-pointers since pointers have to
    be converted to host memory addresses.
    Example for pointer:     guest_mem+(size_t)args->param
    Example for non-pointer: args->param

    Args:
      param: The parameter type and name as a single string.

    Returns:
      Generated parameter,
    """
    param_name = param.split(" ")[-1]
    if "**" in param:
      host_param = "/* TODO: param {0}*/".format(param_name)
    elif "*" in param:
      host_param = "guest_mem+(size_t)args->{0}".format(param_name)
    else:
      host_param = "{0}".format(param_name)

    return host_param
    
  struct_name = get_struct_name(function_name)

  fcn = "{0}void call_{1}(struct kvm_run * run, uint8_t * guest_mem) {{".format(NEWLINES[1], function_name)
  fcn += "{0}{1}unsigned data = *((unsigned*)((size_t)run+run->io.data_offset));".format(NEWLINES[1], TABS[1])
  fcn += "{0}{1}{2} * args = ({2} *) (guest_mem + data);".format(NEWLINES[1], TABS[1], struct_name)
  fcn += "{0}{1}{2} host_ret = {1}(".format(NEWLINES[2], TABS[1], ret, function_name)

  for param in params[:-1]:
    fcn += generate_host_call_parameter(param) + ", "
  else:
    fcn += generate_host_call_parameter(params[-1]) + ");"
  
  if "**" in ret:
    fcn += "{0}{1}// TODO: Take care of {2} return value.".format(NEWLINES[1], TABS[1], ret)
  elif "*" in ret:
    fcn += "{0}{1}memcpy(guest_mem+(size_t)args->ret, host_ret, sizeof(host_ret));".format(NEWLINES[1], TABS[1])
    fcn += "{0}{1}// TODO: Convert ptrs contained in return value.".format(NEWLINES[1], TABS[1])
    fcn += "{0}{1}// TODO: Delete host_ret data structure.".format(NEWLINES[1], TABS[1])
  else:
    fcn += "{0}{1}args->ret = host_ret;".format(NEWLINES[1], TABS[1])

  fcn += "{0}}}{0}".format(NEWLINES[1])

  return fcn


def generate_port_enum(function_names):
  """Generates the enum mapping KVM exit IO port names to port numbers.

  Args:
    function_names: All function names to be mapped to ports as list of strings.

  Returns:
    Generated complete enum.
  """
  port_enum = "typedef enum {"
  for num, function_name in enumerate(function_names, PORT_NUMBER_START):
    port_enum += "\n\tUHYVE_PORT_{0} = 0x{1},".format(function_name.upper(),
                                                    format(num, "X"))
  port_enum += "\n} uhyve_ibv_t;"

  return port_enum


def generate_port_macros(function_names):
  """Generates the compiler macros mapping KVM exit IO port names to port numbers.

  Args:
    function_names: All function names to be mapped to ports as list of strings.

  Returns:
    Generated list of compiler macros.
  """
  macros = ""
  for num, function_name in enumerate(function_names, PORT_NUMBER_START):
    macros += "\n#define UHYVE_PORT_{0} 0x{1},".format(function_name.upper(),
                                                       format(num, "X"))
  return macros


if __name__ == "__main__":
  with open(SRC_PATH, "r") as f_src, \
          open(IBV_GEN_PATH, "w") as f_ibv, \
          open(UHYVE_HOST_FCNS_GEN_PATH, "w") as f_uhyve_host_fncs, \
          open(UHYVE_IBV_HEADER_STRUCTS_GEN_PATH, "w") as f_structs:
    function_names = []
    for line in f_src:
      ret, function_name, params = parse_line(line)
      function_names.append(function_name)

      struct = generate_struct(ret, function_name, params)
      f_ibv.write(struct)
      f_structs.write(struct)

      kernel_function = generate_kernel_function(ret, function_name, params)
      f_ibv.write(kernel_function)

      uhyve_fnc = generate_uhyve_host_function(ret, function_name, params)
      f_uhyve_host_fncs.write(uhyve_fnc)

  with open(UHYVE_IBV_HEADER_GEN_PATH, "w") as f_uhyve_ibv:
    port_enum = generate_port_enum(function_names)
    f_uhyve_ibv.write(port_enum)

  with open(UHYVE_CASES_GEN_PATH, "w") as f_cases:
    uhyve_cases = generate_uhyve_cases(function_names)
    f_cases.write(uhyve_cases)

  with open(INCLUDE_STDDEF_GEN_PATH, "w") as f_stddef:
    port_macros = generate_port_macros(function_names)
    f_stddef.write(port_macros)
