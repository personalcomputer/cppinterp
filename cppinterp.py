#!/usr/bin/env python
# -*- coding: utf-8 -*-

#This is designed to allow very quick and easy testing of small bits of C++ functionality through small snippets of code in a faked 'interpreter'-like CLI environment. It's not quite a REPL, as it does not print the result of everything.

import os
import sys
import subprocess
import re

temp_directory = '/tmp/cppinterp'
temp_src_filename_nopath = 'cppinterp.cpp'
temp_src_filename = temp_directory+'/'+temp_src_filename_nopath
temp_bin_filename = temp_directory+'/cppinterp.run'
temp_errlog_filename = temp_directory+'/cxx_err.log'
temp_outlog_filename = temp_directory+'/cxx_out.log'

extra_gcc_flags = []#, '-std=c++11']

codewrap_top = '''using namespace std;
'''
codewrap_mid = '''int main()
{
'''
codewrap_bottom = '''  return 0;
}
'''
codewrap_top_tot_lines = len(codewrap_top.split('\n'))
codewrap_mid_tot_lines = len(codewrap_mid.split('\n'))

OS_CLEAR_CMD = {'nt':'cls', 'posix':'clear'}[os.name]


def clean_gcc_error_from_wrapped_code(error, src):
  src_lines = src.split('\n')
  src_tot_lines = len(src_lines)

  #error = error[:error.rfind('\n')]
  error = re.sub('('+temp_src_filename+'|'+temp_src_filename_nopath+r'):', '', error)
  error = re.sub(r' In function ‘int main\(\)’:\n', '', error)

  #Completely rewrite any errors that look like "error: expected ‘;’ before ‘return’" so that they make sense within the contex tof what the user wrote, dropping the reference to return statement they didn't write.
  error = re.sub(str(src_tot_lines-2)+r':3: error: expected (‘.+’|\w+) before ‘return’', str(src_tot_lines-3)+':'+str(len(src_lines[src_tot_lines-4])+1)+r': error: expected \1', error)

  error = re.sub('compilation terminated.\n\s*\n?','',error)

  return error

def strip_make_output(compile_output):
  compile_output = re.sub(r'(Super)?make: .+', '', compile_output)
  compile_output = re.sub(r'g\+\+ .+', '', compile_output)
  compile_output = re.sub(r'rm -f .+', '', compile_output)
  return compile_output

def execute_wrapped_code(uses_custom_headers, outmain_code, inmain_code): #returns (code_status_bool (Did it compile & execute OK?), trimmed_cxx_output (Not program output - this should exclusively contain errors and warnings from compiling))
  os.system('mkdir -p '+temp_directory)

  src = open(temp_src_filename, 'w')
  src_code = codewrap_top+outmain_code+codewrap_mid+inmain_code+codewrap_bottom
  src.write(codewrap_top+outmain_code+codewrap_mid+inmain_code+codewrap_bottom)
  src.close()

  use_supermake = uses_custom_headers #custom headers included, possibly libraries that may require fancy Lflags or Cflags -- Use Supermake to handle, instead of raw gcc

  cmd = []
  if use_supermake:
    cmd = ['supermake','--quiet','--no-run','--binary='+temp_bin_filename]
    if extra_gcc_flags:
      cmd.append('--custom='+''.join(extra_gcc_flags))
  else: #for speed & compatibility
    cmd = ['g++', temp_src_filename, '-o', temp_bin_filename]
    if extra_gcc_flags:
      cmd.extend(extra_gcc_flags)
  compile_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=temp_directory)

  compile_status = compile_proc.wait()
  compile_status_ok = compile_status == 0

  compile_err = compile_proc.stderr.read()
  compile_out = compile_proc.stdout.read()

  errlog = open(temp_errlog_filename, 'w')
  errlog.write(compile_err)
  errlog.close()
  outlog = open(temp_outlog_filename, 'w')
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
    prog_run_status_ok = subprocess.call([temp_bin_filename]) == 0
    return (prog_run_status_ok, compile_out+compile_err)

  return (compile_status_ok, compile_out+compile_err)

def adjust_gcc_line_reference(line_number, new_code_tot_lines, outmain_code_tot_lines, inmain_code_tot_lines):
  if line_number >= codewrap_top_tot_lines+outmain_code_tot_lines+codewrap_mid_tot_lines-2:
    line_number -= codewrap_top_tot_lines+outmain_code_tot_lines+codewrap_mid_tot_lines-2
    line_number -= inmain_code_tot_lines-1
  else:
    line_number -= codewrap_top_tot_lines
    line_number -= outmain_code_tot_lines-1

  line_number += new_code_tot_lines

  return line_number

def adjust_gcc_line_references(errors, new_code_tot_lines, outmain_code_tot_lines, inmain_code_tot_lines): #line references are relative to their position in either inmain_code or outmain_code, depending on where the error (line reference) is
  return re.sub(r'(\d+):(\d+):', lambda matchobj: str(adjust_gcc_line_reference(int(matchobj.group(1)), new_code_tot_lines, outmain_code_tot_lines, inmain_code_tot_lines))+':'+matchobj.group(2)+':', errors)

def determine_if_code_needs_main(code): #Determine if the code is a declaration/definition/include or if it is instructions that are intended to be ran within a function ('needs main')
  if re.match(r'\s*\#include', code):
    return False
  if re.match(r'\s*[a-zA-Z0-9_]+[ \*]*[a-zA-Z0-9_]+ ?\(([a-zA-Z0-9_]+[ \*]*[a-zA-Z0-9_]+,?)*\)', code): #function declaration or definition
    return False
  if re.match(r'\s*(class|typedef|namespace|template)', code): #look for keywords
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
  return persistant_code

def main():
  try:
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
    input_history = []

    while True:
      new_code = raw_input(">>> ")
      history_itr = 0
      while new_code.endswith(chr(0x1B)+'[A'):
        history_itr += 1
        if history_itr <= len(input_history):
          new_code = input_history[-history_itr]+raw_input(">>> "+input_history[-history_itr])
        else:
          new_code = raw_input(">>> ")

      input_history.append(new_code)

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
        input_history.append(new_line)
        new_code += '\n'+new_line

      else:
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

        (code_status, compile_out) = execute_wrapped_code(uses_custom_headers, outmain_code, inmain_code)
        if compile_out:
          print(adjust_gcc_line_references(compile_out, len(new_code.split('\n')), len(outmain_code.split('\n')), len(inmain_code.split('\n'))))
        if code_status: #there were no errors
          auto_headers = auto_headers.union(new_auto_headers)
          if new_code_inmain:
            inmain_code_history += parse_persistant_code(new_code)
          else:
            outmain_code_history += parse_persistant_code(new_code)

  except KeyboardInterrupt:
    print('')


if __name__ == '__main__':
  main()
