#!/usr/bin/python

from sys import argv, exit
from modules.git_core import get_current_branch
from modules.git_format import format_blanks


current_branch = get_current_branch()

branch_identificator = current_branch.split('/')[0]
if branch_identificator not in ['FEATURE', 'HOTFIX', 'BUGFIX']:
    exit(0)

with open(argv[1], 'r') as file:
    content = file.read()
    if not content.startswith(current_branch):
        print(format_blanks("Abort: Commit message require prefix branch name. Try 'git cmsg'"))
        exit(1)
