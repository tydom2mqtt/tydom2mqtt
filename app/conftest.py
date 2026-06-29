import os
import sys

# The application modules import each other as top-level packages (e.g.
# `from configuration.Configuration import Configuration`), matching the
# container's WORKDIR /app. Put this directory on sys.path so tests resolve
# imports the same way regardless of how pytest is invoked.
sys.path.insert(0, os.path.dirname(__file__))
