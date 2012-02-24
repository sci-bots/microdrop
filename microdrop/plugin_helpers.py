from app_context import get_app
from plugin_manager import emit_signal, IPlugin

class AppDataController(object):
    def get_default_app_options(self):
        return dict([(k, v.value) for k,v in self.AppFields.from_defaults().iteritems()])

    def get_app_form_class(self):
        return self.AppFields

    def get_app_fields(self):
        return self.AppFields.field_schema_mapping.keys()

    def get_app_values(self):
        if not hasattr(self, 'name'):
            raise NotImplementedError
        app = get_app()
        return app.get_data(self.name)

    def set_app_values(self, values_dict):
        if not hasattr(self, 'name'):
            raise NotImplementedError
        elements = self.AppFields(value=values_dict)
        if not elements.validate():
            raise ValueError('Invalid values: %s' % elements.errors)
        app = get_app()
        app_data = app.get_data(self.name)
        values = dict([(k, v.value) for k, v in elements.iteritems()])
        if app_data:
            app_data.update(values)
        else:
            app.set_data(self.name, values)
        emit_signal('on_app_options_changed', [self.name], interface=IPlugin)

