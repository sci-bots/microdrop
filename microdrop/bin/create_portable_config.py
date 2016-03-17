import os
import sys
import pkg_resources

from path_helpers import path
import jinja2


config_template = '''
data_dir = .
[plugins]
        # directory containing microdrop plugins
        directory = plugins
[microdrop.gui.experiment_log_controller]
        notebook_directory = notebooks
[microdrop.gui.dmf_device_controller]
        device_directory = devices
'''

launcher_template = '''
REM Change into [parent directory of batch file][1].
REM
REM [1]: http://stackoverflow.com/questions/16623780/how-to-get-windows-batchs-parent-folder
cd %~dp0
REM Launch Microdrop
{{ py_exe }} -m microdrop.microdrop -c %~dp0microdrop.ini
'''


def parse_args(args=None):
    '''Parses arguments, returns (options, args).'''
    from argparse import ArgumentParser

    if args is None:
        args = sys.argv

    parser = ArgumentParser(description='Create portable MicroDrop settings '
                            'directory.')
    parser.add_argument('output_dir', type=path)

    args = parser.parse_args()
    return args


def main(output_dir):
    output_dir = path(output_dir)

    if not output_dir.isdir():
        output_dir.makedirs_p()
    elif list(output_dir.files()):
        raise IOError('Output directory exists and is not empty.')

    config_path = output_dir.joinpath('microdrop.ini')
    with config_path.open('wb') as output:
        template = jinja2.Template(config_template)
        config_str = template.render(output_dir=output_dir.name)
        output.write(config_str)

    py_exe = path(sys.executable).abspath()
    launcher_path = output_dir.joinpath('microdrop.bat')
    with launcher_path.open('wb') as output:
        template = jinja2.Template(launcher_template)
        launcher_str = template.render(working_dir=output_dir.abspath(),
                                       py_exe=py_exe,
                                       config_path=config_path.abspath())
        output.write(launcher_str)

    print 'Start MicroDrop with the following:'
    print '\n    %s' % launcher_path.abspath()


if __name__ == '__main__':
    args = parse_args()
    main(args.output_dir)
