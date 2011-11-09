import uuid
import re

import jinja2
from path import path


clean_id = lambda x: re.sub(r'[\\\/\.]', '_', x)

component_template = '''\
    <Component Id='{{ id }}' Guid='{{ uuid }}'>
        <File Id='f{{ id }}' Name='{{ filename }}' DiskId='1' Source='{{ source }}' />
    </Component>'''

feature_template = '''\
    <Feature Id='{{ id }}' Title='{{ title }}' Level='1'>{% for comp_id in components %}
        <ComponentRef Id='{{ comp_id }}' />{% endfor %}
    </Feature>'''


if __name__ == '__main__':
    t = jinja2.Template(component_template)
    files = path('.').files('*.log')
    components = []

    for f in files:
        md5 = f.read_md5()
        md5.update(f)
        guid = md5.hexdigest()[:16]
        comp_id = clean_id(f)
        print t.render(dict(id=comp_id,
            uuid=uuid.UUID(bytes=guid),
            filename=f.name,
            source=f))
        components.append(comp_id)

    t2 = jinja2.Template(feature_template)
    print t2.render(dict(id='microdrop', title='microdrop',
                    components=components))
