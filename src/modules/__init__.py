import os, sys, inspect

folder = os.path.realpath(os.path.abspath(
        os.path.split(inspect.getfile(inspect.currentframe()))[0]))

if folder not in sys.path:
    sys.path.insert(0, folder)