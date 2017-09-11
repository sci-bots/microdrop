call Scripts\activate.bat & python -m mpm.bin.api enable droplet_planning_plugin dmf_device_ui_plugin dropbot_plugin user_prompt_plugin step_label_plugin
if errorlevel 1 exit 1
call Scripts\activate.bat & python -c "import yaml; output = open('.condarc', 'w'); output.write(yaml.dump({'channels': ['sci-bots', 'microdrop-plugins', 'wheeler-microfluidics', 'conda-forge', 'defaults']}))"
if errorlevel 1 exit 1
