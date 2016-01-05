import sys

import pandas as pd
from path_helpers import path


def main(root, old_name, new_name):
    names = pd.Series([old_name, new_name], index=['old', 'new'])
    underscore_names = names.map(lambda v: v.replace('-', '_'))
    camel_names = names.str.split('-').map(lambda x: ''.join([y.title()
                                                              for y in x]))

    # Replace all occurrences of provided original name with new name, and all
    # occurrences where dashes (i.e., '-') are replaced with underscores.
    #
    # Dashes are used in Python package names, but underscores are used in
    # Python module names.
    for p in path(root).walkfiles():
        data = p.bytes()
        if '.git' not in p and (names.old in data or
                                underscore_names.old in data or
                                camel_names.old in data):
            p.write_bytes(data.replace(names.old, names.new)
                          .replace(underscore_names.old, underscore_names.new)
                          .replace(camel_names.old, camel_names.new))

    def rename_path(p):
        if '.git' in p:
            return
        if underscore_names.old in p.name:
            p.rename(p.parent.joinpath(p.name.replace(underscore_names.old,
                                                      underscore_names.new)))
        if camel_names.old in p.name:
            p.rename(p.parent.joinpath(p.name.replace(camel_names.old,
                                                      camel_names.new)))

    # Rename all files/directories containing original name with new name, and
    # all occurrences where dashes (i.e., '-') are replaced with underscores.
    #
    # Process list of paths in *reverse order* to avoid renaming parent
    # directories before children.
    for p in sorted(list(path(root).walkdirs()))[-1::-1]:
        rename_path(p)

    for p in path(root).walkfiles():
        rename_path(p)


def parse_args(args=None):
    """Parses arguments, returns (options, args)."""
    from argparse import ArgumentParser

    if args is None:
        args = sys.argv

    parser = ArgumentParser(description='Rename template project with'
                            'hyphen-separated <new name> (path names and in '
                            'files).')
    parser.add_argument('new_name', help='New project name (e.g., '
                        ' `my-new-project`)')

    args = parser.parse_args()
    return args


if __name__ == '__main__':
    args = parse_args()
    main('.', 'zmq-hub-plugin', args.new_name)
