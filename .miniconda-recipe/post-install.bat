REM Link installed plugins into Conda MicroDrop activated plugins directory.
call Scripts\activate.bat . & python -m mpm.bin.api enable droplet_planning_plugin dmf_device_ui_plugin dropbot_plugin user_prompt_plugin step_label_plugin

REM Load plugins by default
call Scripts\activate.bat . & microdrop-config edit --append plugins.enabled droplet_planning_plugin
call Scripts\activate.bat . & microdrop-config edit --append plugins.enabled dmf_device_ui_plugin
call Scripts\activate.bat . & microdrop-config edit --append plugins.enabled dropbot_plugin
call Scripts\activate.bat . & microdrop-config edit --append plugins.enabled user_prompt_plugin
call Scripts\activate.bat . & microdrop-config edit --append plugins.enabled step_label_plugin
