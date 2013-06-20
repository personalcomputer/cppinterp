#!/usr/bin/env python
# -*- coding: utf-8 -*-

#This is designed to allow very quick and easy testing of small bits of C++ functionality through small snippets of code in a faked 'interpreter'-like CLI environment. It's not quite a REPL, as it does not print the result of everything.

import os
import sys
import subprocess
import re
import readline

USAGE = '''Usage: cppinterp [CXX_OPTIONS]
Launches a C++ REPL-like environment.

More info: <https://github.com/personalcomputer/cppinterp>'''

TEMP_DIRECTORY = '/tmp/cppinterp'
TEMP_SRC_FILENAME_NOPATH = 'cppinterp.cpp'
TEMP_SRC_FILENAME = TEMP_DIRECTORY+'/'+TEMP_SRC_FILENAME_NOPATH
TEMP_BIN_FILENAME = TEMP_DIRECTORY+'/cppinterp.run'
TEMP_ERRLOG_FILENAME = TEMP_DIRECTORY+'/cxx_err.log'
TEMP_OUTLOG_FILENAME = TEMP_DIRECTORY+'/cxx_out.log'

CODEWRAP_TOP = '''using namespace std;
'''
CODEWRAP_MID = '''int main()
{
'''
CODEWRAP_BOTTOM = '''  return 0;
}
'''
CODEWRAP_TOP_TOT_LINES = len(CODEWRAP_TOP.split('\n'))
CODEWRAP_MID_TOT_LINES = len(CODEWRAP_MID.split('\n'))

OS_CLEAR_CMD = {'nt':'cls', 'posix':'clear'}[os.name]

HELP_ARGUMENTS = set(['--help', '-help', '-h', '--h', 'h', '-?', 'help', '/h', '/?', '?', 'HELP'])

def clean_gcc_error_from_wrapped_code(error, src):
  src_lines = src.split('\n')
  src_tot_lines = len(src_lines)

  #error = error[:error.rfind('\n')]
  error = re.sub('('+TEMP_SRC_FILENAME+'|'+TEMP_SRC_FILENAME_NOPATH+r'):', '', error)
  error = re.sub(r' In function ‘int main\(\)’:\n', '', error)

  #Completely rewrite any errors that look like "error: expected ‘;’ before ‘return’" so that they make sense within the contex tof what the user wrote, dropping the reference to return statement they didn't write.
  error = re.sub(str(src_tot_lines-2)+r':3: error: expected (‘.+’|[\w-]+) before ‘return’', str(src_tot_lines-3)+':'+str(len(src_lines[src_tot_lines-4])+1)+r': error: expected \1', error)

  error = re.sub('compilation terminated.\n','',error)

  return error

def strip_make_output(compile_output):
  compile_output = re.sub(r'(Super)?make: .+', '', compile_output)
  compile_output = re.sub(r'g\+\+ .+', '', compile_output)
  compile_output = re.sub(r'rm -f .+', '', compile_output)
  return compile_output

def execute_wrapped_code(uses_custom_headers, outmain_code, inmain_code, extra_gcc_flags): #returns (code_status_bool (Did it compile & execute OK?), trimmed_err, trimmed_out (Not program output - this should exclusively contain errors and warnings from compiling))
  os.system('mkdir -p '+TEMP_DIRECTORY)

  src = open(TEMP_SRC_FILENAME, 'w')
  src_code = CODEWRAP_TOP+outmain_code+CODEWRAP_MID+inmain_code+CODEWRAP_BOTTOM
  src.write(CODEWRAP_TOP+outmain_code+CODEWRAP_MID+inmain_code+CODEWRAP_BOTTOM)
  src.close()

  use_supermake = uses_custom_headers #custom headers included, possibly libraries that may require fancy Lflags or Cflags -- Use Supermake to handle, instead of raw gcc

  supermake_cmd = ['supermakea','--quiet','--no-run','--binary='+TEMP_BIN_FILENAME]
  if extra_gcc_flags:
    supermake_cmd.append('--custom='+''.join(extra_gcc_flags))

  gcc_cmd = ['g++', TEMP_SRC_FILENAME, '-o', TEMP_BIN_FILENAME]
  if extra_gcc_flags:
    gcc_cmd.extend(extra_gcc_flags)

  compile_proc = None
  if use_supermake:
    try:
      compile_proc = subprocess.Popen(supermake_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=TEMP_DIRECTORY)
    except OSError:
      compile_proc = subprocess.Popen(gcc_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=TEMP_DIRECTORY)
  else:
    compile_proc = subprocess.Popen(gcc_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=TEMP_DIRECTORY)

  compile_status = compile_proc.wait()
  compile_status_ok = compile_status == 0

  compile_err = compile_proc.stderr.read()
  compile_out = compile_proc.stdout.read()

  errlog = open(TEMP_ERRLOG_FILENAME, 'w')
  errlog.write(compile_err)
  errlog.close()
  outlog = open(TEMP_OUTLOG_FILENAME, 'w')
  outlog.write(compile_out)
  outlog.close()

  compile_out = compile_out.strip()
  compile_err = compile_err.strip()

  if use_supermake:
    compile_out = strip_make_output(compile_out)
    compile_err = strip_make_output(compile_err)
  compile_err = clean_gcc_error_from_wrapped_code(compile_err, src_code)

  compile_out = compile_out.strip()
  compile_err = compile_err.strip()

  if compile_status_ok:
    prog_run_status_ok = subprocess.call([TEMP_BIN_FILENAME]) == 0
    return (prog_run_status_ok, compile_err, compile_out)

  return (compile_status_ok, compile_err, compile_out)

def adjust_gcc_line_reference(line_number, new_code_tot_lines, outmain_code_tot_lines, inmain_code_tot_lines):
  if line_number >= CODEWRAP_TOP_TOT_LINES+outmain_code_tot_lines+CODEWRAP_MID_TOT_LINES-2:
    line_number -= CODEWRAP_TOP_TOT_LINES+outmain_code_tot_lines+CODEWRAP_MID_TOT_LINES-2
    line_number -= inmain_code_tot_lines-1
  else:
    line_number -= CODEWRAP_TOP_TOT_LINES
    line_number -= outmain_code_tot_lines-1

  line_number += new_code_tot_lines

  return line_number

def adjust_gcc_errline(matchobj, new_code_tot_lines, outmain_code_tot_lines, inmain_code_tot_lines):
  line_number = int(matchobj.group(1))
  line_number = adjust_gcc_line_reference(line_number, new_code_tot_lines, outmain_code_tot_lines, inmain_code_tot_lines)
  if line_number > 0:
    return str(line_number)+matchobj.group(2)
  else:
    return ''

def adjust_gcc_line_references(errors, new_code_tot_lines, outmain_code_tot_lines, inmain_code_tot_lines): #line references are relative to their position in either inmain_code or outmain_code, depending on where the error (line reference) is
  return re.sub(r'(\d+)(:\d+: .+\n?)', lambda matchobj: adjust_gcc_errline(matchobj, new_code_tot_lines, outmain_code_tot_lines, inmain_code_tot_lines), errors)

def determine_if_code_needs_main(code): #Determine if the code is a declaration/definition/include or if it is instructions that are intended to be ran within a function ('needs main')
  if re.match(r'\s*\#include', code):
    return False
  if re.match(r'\s*[a-zA-Z0-9_]+[ \*]*[a-zA-Z0-9_]+ ?\(([a-zA-Z0-9_]+[ \*]*[a-zA-Z0-9_]+,?)*\)', code): #function declaration or definition
    return False
  if re.match(r'\s*(class|typedef|namespace|template|enum)', code): #look for keywords
     return False
  return True

def determine_needed_headers(code): #hueristic to speed things up
  needed_headers = set([])
  if re.search('(std::)?string ', code):
    needed_headers.add('#include <string>')
  if re.search('(std::)?(cout|endl|cin)', code):
    needed_headers.add('#include <iostream>')
  if re.search('(std::)?stringstream ', code):
    needed_headers.add('#include <sstream>')
  if re.search('printf\(', code):
    needed_headers.add('#include <cstdio>')
    needed_headers.add('#include <cstdlib>')

  return needed_headers

def parse_persistant_code(code):
  #Given a bit of code, return the code that modifies persistant internal state. ie: does not output to the sceen or similar

  #This currently only supports std::cout, and probably won't ever support much more.

  persistant_code = re.sub(r'\s*<<', ';\n', re.sub(r'(?:std::)?cout\s*<<\s*((?:\s*.+\s*<<)+\s*.+\s*)', r'\1', code))
  persistant_code = re.sub(r'\s*(std::)?endl\s*;', '', persistant_code)
  persistant_code = re.sub(r'printf\(".+"\s*,?((?:.+\s*,\s*)*.+)\s*\);', lambda m: ''.join([stmt+';\n' for stmt in m.group(1).split(',')]), persistant_code)

  return persistant_code

def main():
  try:
    if HELP_ARGUMENTS & set(sys.argv[1:]):
      print(USAGE)
      sys.exit(0)

    extra_gcc_flags = sys.argv[1:];

    if extra_gcc_flags:
      #quickly test to make sure they are valid
      (code_status, compile_err, compile_out) = execute_wrapped_code(False,'','',extra_gcc_flags)
      if not code_status:
        print(compile_err)
        sys.exit(1)


    #Basic flow:
    #-> Render prompt ">>>"
    #-> Wait for user to hit [ENTER]
    #-> Execute provided input (with helper C++ funcs & libraries)
    #-> Display execution output. (This is not REPL, even though it provides most of the functionality of one! I don't want to parse C++.)
    #-> If there was an error: Display the error, but modify line/numbers to match the input.
    #-> Add new code to the code history that is re-executed everytime to give the appearance of persistant state
    #-> Repeat

    auto_headers = set([])
    outmain_code_history = "" #code that should be placed raw in the file
    inmain_code_history = "" #code that should be placed within a function (the main function) in order to execute

    while True:
      new_code = raw_input(">>> ")

      if re.match(r'\.?cl(ear|s)', new_code):
        os.system(OS_CLEAR_CMD)
        continue;

      if re.match(r'\.?(quit|exit)', new_code):
        break;

      while new_code.endswith('...') or new_code.endswith('\\'):
        if new_code.endswith('...'):
          new_code = new_code[:-3]
        elif new_code.endswith('\\'):
          new_code = new_code[:-1]

        new_line = raw_input("... ")
        new_code += '\n'+new_line

      if not new_code.strip():
        continue;

      #if not new_code.endswith(';'):
      #  new_code += ';'

      new_code += '\n'

      new_code_inmain = determine_if_code_needs_main(new_code)
      outmain_code = outmain_code_history
      inmain_code = inmain_code_history
      if new_code_inmain:
        inmain_code += new_code
      else:
        outmain_code += new_code

      uses_custom_headers = outmain_code.find('#include') != -1

      new_auto_headers = determine_needed_headers(new_code);
      outmain_code = '\n'.join(auto_headers.union(new_auto_headers))+'\n'+outmain_code

      (code_status, compile_err, compile_out) = execute_wrapped_code(uses_custom_headers, outmain_code, inmain_code, extra_gcc_flags)
      if compile_out or compile_err:
        print(adjust_gcc_line_references(compile_out+compile_err, len(new_code.split('\n')), len(outmain_code.split('\n')), len(inmain_code.split('\n'))).strip())
      if code_status: #there were no errors
        auto_headers = auto_headers.union(new_auto_headers)
        if new_code_inmain:
          inmain_code_history += parse_persistant_code(new_code)
        else:
          outmain_code_history += parse_persistant_code(new_code)

  except (KeyboardInterrupt, EOFError):
    print('')


if __name__ == '__main__':
  main()