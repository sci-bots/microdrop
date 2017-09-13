'''
Show or edit MicroDrop configuration.

.. versionadded:: 2.13
'''
import argparse
import io
import json
import re
import sys

import configobj
import microdrop as md
import microdrop.config
import pydash
import yaml


def _config_parser():
    parser = argparse.ArgumentParser(parents=[md.MICRODROP_PARSER],
                                     add_help=False)

    subparsers = parser.add_subparsers(dest='command', help='commands')

    subparsers.add_parser('locate', help='Show path to configuration '
                          'source')

    show = subparsers.add_parser('show', help='Show configuration')
    show.add_argument('--get', metavar='KEY')
    show_format = show.add_mutually_exclusive_group()
    show_format.add_argument('--json', action='store_true')
    show_format.add_argument('--yaml', action='store_true')

    edit = subparsers.add_parser('edit', help='Modify configuration')
    edit.add_argument('-n', '--dry-run', action='store_true')
    edit_args = edit.add_mutually_exclusive_group(required=True)
    edit_args.add_argument('--append', nargs=2, metavar=('KEY', 'VALUE'),
                           help='Add one configuration value to the beginning '
                           'of a list key.')
    edit_args.add_argument('--prepend', nargs=2, metavar=('KEY', 'VALUE'),
                           help='Add one configuration value to the end of a '
                           'list key.')
    edit_args.add_argument('--set', nargs=2, metavar=('KEY', 'VALUE'),
                           help='Set a boolean or string key')
    edit_args.add_argument('--remove', nargs=2, metavar=('KEY', 'VALUE'),
                           help='Remove all instances of configuration value '
                           'from a list key.')
    edit_args.add_argument('--remove-key', metavar='KEY', help='Remove a '
                           'configuration key (and all its values).')
    return parser


CONFIG_PARSER = _config_parser()


def parse_args(args=None):
    """Parses arguments, returns (options, args)."""
    if args is None:
        args = sys.argv[1:]

    parser = argparse.ArgumentParser(parents=[CONFIG_PARSER])
    args = parser.parse_args(args)
    return args


def main(args=None):
    '''
    Wrap :func:`config` with integer return code.

    Parameters
    ----------
    args : argparse.Namespace, optional
        Arguments as parsed by :func:`parse_args`.

    See also
    --------
    :func:`parse_args`
    '''
    config(args)
    # Return
    return 0


def config(args=None):
    '''
    Parameters
    ----------
    args : argparse.Namespace, optional
        Arguments as parsed by :func:`parse_args`.

    See also
    --------
    :func:`parse_args`

    Returns
    -------
    configobj.ConfigObj
        Parsed (and potentially modified) configuration.
    '''
    if args is None:
        args = parse_args()

    config = md.config.Config(args.config)

    if args.command == 'locate':
        print config.filename
    elif args.command == 'show':
        if args.get:
            data = pydash.get(config.data.dict(), args.get)
        else:
            data = config.data.dict()

        if args.json:
            # Output in JSON.
            json.dump(obj=data, fp=sys.stdout, indent=4)
        elif args.yaml:
            # Output in YAML format.
            print yaml.dump(data, default_flow_style=False),
        elif isinstance(data, dict):
            # Output in `ini` format.
            output = io.BytesIO()
            configobj.ConfigObj(data).write(output)
            print output.getvalue(),
        else:
            print data
    elif args.command == 'edit':
        for action_i in ('append', 'prepend', 'set', 'remove', 'remove_key'):
            if getattr(args, action_i):
                action = action_i
                break

        if action in ('append', 'prepend', 'set', 'remove'):
            # Unpack key and new value.
            key, new_value = getattr(args, action)

            # Look up existing value.
            config_value = pydash.get(config.data, key)

            if action == 'set':
                # Set a key to a string value.

                # Create dictionary structure containing only the specified key
                # and value.
                nested_value = pydash.set_({}, key, new_value)
                # Merge nested value into existing configuration structure.
                pydash.merge(config.data, nested_value)
            else:
                # Action is a list action.

                if config_value is None:
                    # Create dictionary structure containing only empty list for
                    # specified key.
                    config_value = []
                    nested_value = pydash.set_({}, key, config_value)
                    # Merge nested value into existing configuration structure.
                    pydash.merge(config.data, nested_value)
                elif not isinstance(config_value, list):
                    print >> sys.stderr, 'Value at %s is not a list.' % key
                    raise SystemExit(1)

                if new_value in config_value:
                    # Remove value even if we are appending or prepending to
                    # avoid duplicate values.
                    config_value.remove(new_value)

                if args.append:
                    config_value.append(new_value)
                elif args.prepend:
                    config_value.insert(0, new_value)
        elif action == 'remove_key':
            key = getattr(args, action)

            if pydash.get(config.data, key) is not None:
                # Key exists.

                # Split key into levels.
                # Use [negative lookbehind assertion][1] to only split on
                # non-escaped '.' characters.
                #
                # [1]: https://stackoverflow.com/a/21107911/345236
                levels = re.split(r'(?<!\\)\.', key)
                parents = levels[:-1]

                parent = config.data

                for parent_i in parents:
                    parent = parent[parent_i]

                # Delete key from deepest parent.
                del parent[levels[-1]]
        if args.dry_run:
            output = io.BytesIO()
            config.data.write(output)
            print output.getvalue(),
        else:
            config.save()
    return config


if __name__ == '__main__':
    config_ = config(parse_args())
