import uuid
import re

import jinja2
from path import path


WXS_TEMPLATE = '''\
<?xml version='1.0'?><Wix xmlns='http://schemas.microsoft.com/wix/2006/wi'>
   <Product Id='*' Name='MicroDrop' Language='1033'
            Version='1.0.0.0' Manufacturer='Wheeler Microfluidics Lab' UpgradeCode='048f3511-0a49-11e1-a03e-080027963a76'>
      <Package Description='microdrop'
                Comments='microdrop'
                Manufacturer='Wheeler Microfluidics Lab' InstallerVersion='200' Compressed='yes' />
 
      <Media Id='1' Cabinet='product.cab' EmbedCab='yes' />
 
      <Directory Id='TARGETDIR' Name='SourceDir'>
         <Directory Id='ProgramFilesFolder' Name='PFiles'>
            <Directory Id='microdrop' Name='MicroDrop Program'>{% for c in components %}
                <Component Id='{{ c.id }}' Guid='{{ c.guid }}'>
                    <File Id='f{{ c.id }}' Name='{{ c.filename }}' DiskId='1' Source='{{ c.source }}' />
                </Component>{% endfor %}
            </Directory>
         </Directory>
      </Directory>
 
    <Feature Id='{{ id }}' Title='{{ title }}' Level='1'>{% for c in components %}
        <ComponentRef Id='{{ c.id }}' />{% endfor %}
    </Feature>

   </Product>
</Wix>'''


class Component(object):
    def __init__(self, filepath):
        self.filepath = path(filepath)
        self.guid = self._get_guid()
        self.id = self._clean_id(self.filepath)
        self.filename = self.filepath.name
        self.source = self.filepath
        
    def _get_guid(self):
        md5 = self.filepath._hash('md5')
        md5.update(self.filepath)
        return uuid.UUID(bytes=md5.hexdigest()[:16])

    def _clean_id(self, x):
        return re.sub(r'[\\\/\.-]', '_', x)


if __name__ == '__main__':
    files = path('dist\\microdrop').files('microdrop.exe*')
    components = [Component(f) for f in files]

    t = jinja2.Template(WXS_TEMPLATE)

    print t.render(id='microdrop', title='microdrop', components=components)
