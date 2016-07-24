#!/usr/bin/python

from sys import argv, exit
from modules.git_core import *
from modules.git_validation import tag_exists
from modules.git_format import format_blanks

current_branch = get_current_branch()

if tag_exists(testing_tag(current_branch)) or \
   tag_exists(finished_tag(current_branch)) or \
   tag_exists(released_tag(current_branch)):
    print(format_blanks('Abort: Prolong branch before pushing commits on remote.'))
    exit(1)
