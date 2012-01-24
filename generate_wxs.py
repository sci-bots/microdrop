##!/usr/bin/env python
import hashlib
import itertools
import uuid
import re
from xml.dom.minidom import Document

import jinja2
from path import path


WXS_TEMPLATE = '''\
<?xml version='1.0'?><Wix xmlns='http://schemas.microsoft.com/wix/2006/wi'>
    <Product Id='*' Name='Microdrop' Language='1033'
            Version='{{ version }}' Manufacturer='Wheeler Microfluidics Lab'
            UpgradeCode='048f3511-0a49-11e1-a03e-080027963a76'>
        <Package Description='Microdrop'
                Comments='Microdrop'
                Manufacturer='Wheeler Microfluidics Lab'
                InstallerVersion='200' Compressed='yes' />
 
        <Media Id='1' Cabinet='product.cab' EmbedCab='yes' />

        <WixVariable Id="WixUILicenseRtf" Value="License.rtf" />
 
        <Upgrade Id="048f3511-0a49-11e1-a03e-080027963a76">
            <UpgradeVersion OnlyDetect="yes" Minimum="{{ version }}" Property="NEWERVERSIONDETECTED" IncludeMinimum="no" />
            <UpgradeVersion OnlyDetect="no" Maximum="{{ version }}" Property="OLDERVERSIONBEINGUPGRADED" IncludeMaximum="no" />
        </Upgrade>

        <InstallExecuteSequence>
            <RemoveExistingProducts After="InstallInitialize" />
        </InstallExecuteSequence>

        <Icon Id="microdrop.ico" SourceFile="microdrop.ico" />
        <Property Id="ARPPRODUCTICON" Value="microdrop.ico" />

        <Directory Id='TARGETDIR' Name='SourceDir'>
            <Directory Id='ProgramFilesFolder' Name='PFiles'>
{{ dir_tree }}
         </Directory>
        <Directory Id="CommonAppDataFolder">
            <Directory Id='microdrop_app_data' Name='Microdrop'>
{{ device_tree }}
{{ plugins_tree }}
            </Directory>
        </Directory>
         <Directory Id='ProgramMenuFolder'>
            <Directory Id='ApplicationProgramsFolder' Name='Microdrop' />
         </Directory>
      </Directory>

    <!-- Step 2: Add the shortcut to your installer package -->
    <DirectoryRef Id="ApplicationProgramsFolder">
        <Component Id="ApplicationShortcut" Guid="9f3fb577-2e2f-4a53-8df2-9e9f7fcb79a6" >
            <Shortcut Id="ApplicationStartMenuShortcut" Name="Microdrop" 
                Description="My Application Description"
                Target="[{{ root }}]microdrop.exe"
                        WorkingDirectory="{{ root }}"/>
            <RemoveFolder Id="ApplicationProgramsFolder" On="uninstall"/>
            <RegistryValue Root="HKCU" Key="Software\Microsoft\Microdrop" Name="installed" Type="integer" Value="1" KeyPath="yes"/>
        </Component>
    </DirectoryRef>
 
    <Feature Id='{{ id }}' Title='{{ title }}' Level='1'>{% for c in components %}
        <ComponentRef Id='{{ c.id }}' />{% endfor %}
        <ComponentRef Id="ApplicationShortcut" />   
    </Feature>

    <Property Id="WIXUI_INSTALLDIR" Value="{{ root }}" />
    <UIRef Id="WixUI_InstallDir" />

   </Product>
</Wix>'''


def _clean_id(x):
    return re.sub(r'[\\\/\.-]', '_', x)


class Component(object):
    def __init__(self, filepath, root=None):
        self.filepath = path(filepath)
        self.guid = str(self._get_guid())
        #self.id = _clean_id(self.filepath)
        self.id = 'ID__%s' % hashlib.md5(self.filepath).hexdigest().upper()
        if root:
            self.filename = path(root) / self.filepath.name
        else:
            self.filename = self.filepath.name
        self.source = self.filepath
        
    def _get_guid(self):
        md5 = self.filepath._hash('md5')
        md5.update(self.filepath)
        return uuid.UUID(bytes=md5.hexdigest()[:16])

    def __str__(self):
        return '''filepath=%s, guid=%s, id=%s, filename=%s, source=%s''' % (
            self.filepath, self.guid, self.id, self.filename, self.source)


class Directory(object):
    def __init__(self, dirpath, root=None):
        self.dirpath = path(dirpath)
        #self.id = _clean_id(self.dirpath)
        self.id = 'ID__%s' % hashlib.md5(self.dirpath).hexdigest().upper()
        if root:
            self.dirname = path(root) / self.dirpath.name
        else:
            self.dirname = self.dirpath.name


class DirectoryWalker(object):
    def __init__(self):
        self.components = []

    def post_file(self, f, parent, elem):
        parent.appendChild(elem)

    def pre_file(self, f):
        '''
        <Component Id='{{ c.id }}' Guid='{{ c.guid }}'>
            <File Id='f{{ c.id }}' Name='{{ c.filename }}' DiskId='1' Source='{{ c.source }}' />
        </Component>{% endfor %}
        '''
        comp = Component(f)
        self.components.append(comp)
        component = self.doc.createElement('Component')
        component.setAttribute('Id', comp.id)
        component.setAttribute('Guid', comp.guid)
        elem = self.doc.createElement('File')
        elem.setAttribute('Id', 'f%s' % comp.id)
        elem.setAttribute('Name', '%s' % comp.filename)
        elem.setAttribute('Source', '%s' % comp.source)
        component.appendChild(elem)
        return component

    def post_directory(self, d, parent, elem):
        parent.appendChild(elem)
        return parent

    def pre_directory(self, d):
        directory = Directory(d)
        node = self.doc.createElement('Directory')
        node.setAttribute('Id', directory.id)
        node.setAttribute('Name', directory.dirname.name)
        return node

    def xml_tree(self, filepath, recursive=False):
        self.components = []
        self.doc = Document()
        filepath = path(filepath)
        node = self.walk(filepath, recursive)
        return node, self.components

    def walk(self, filepath, recursive=False):
        "Return a document node contains a directory tree for the filepath."
        filepath = path(filepath)
        pre_dir = self.pre_directory(filepath)
        for fullname in filepath.listdir():
            f = fullname.name
            if fullname.isdir():
                if not recursive:
                    continue
                in_dir = self.walk(fullname, recursive)
                post_dir = self.post_directory(fullname, pre_dir, in_dir)
            else:
                pre_file = self.pre_file(fullname)
                post_file = self.post_file(fullname, pre_dir, pre_file)
        return pre_dir



def generate_wxs(root_path, version):
    dw = DirectoryWalker()
    root = dw.xml_tree(root_path)
    etc = dw.xml_tree(root_path.joinpath('etc'), recursive=True)
    devices = dw.xml_tree(root_path.joinpath('devices'), recursive=True)
    gui = dw.xml_tree(root_path.joinpath('gui'), recursive=True)
    mpl_data = dw.xml_tree(root_path.joinpath('mpl-data'), recursive=True)
    plugins = dw.xml_tree(root_path.joinpath('plugins'), recursive=True)
    share = dw.xml_tree(root_path.joinpath('share'), recursive=True)

    children = dict(etc=etc, gui=gui, mpl_data=mpl_data, share=share)
    for c in children.itervalues():
        root[0].appendChild(c[0])

    all_components = list(itertools.chain(*[c[1] for c in children.itervalues()]))
    all_components += root[1] + devices[1] + plugins[1]

    t = jinja2.Template(WXS_TEMPLATE)

    return t.render(id='Microdrop', title='Microdrop',
                    dir_tree=root[0].toprettyxml(indent='  '),
                    device_tree=devices[0].toprettyxml(indent='  '),
                    plugins_tree=plugins[0].toprettyxml(indent='  '),
                    components=all_components,
                    root=root[0].getAttribute('Id'), version=version)


def _parse_args():
    """Parses arguments, returns ``(options, args)``."""
    from argparse import ArgumentParser

    parser = ArgumentParser(description="""\
Generates a WiX input file for Microdrop.""",
                            epilog="""\
(C) 2011  Ryan Fobel and Christian Fobel.""",
                           )
    parser.add_argument('-v', '--version',
                    action='store', dest='version', type=str,
                    required=True,
                    help='install version')
    args = parser.parse_args()
    
    return args




if __name__ == '__main__':
    args = _parse_args()
    root_path = path('dist').joinpath('microdrop')
    print generate_wxs(root_path, args.version)
