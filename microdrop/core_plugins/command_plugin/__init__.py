try:
    import microdrop_plugin
except ImportError:
    import sys

    print >> sys.stderr, 'Error importing command_plugin'
