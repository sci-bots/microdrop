@echo off
REM Explicitly move noarch packages into `Lib/site-packages` as a workaround to
REM [this issue][i86] with lack of `constructor` support for `noarch` packages.
REM
REM [i86]: https://github.com/conda/constructor/issues/86#issuecomment-330863531
IF EXIST site-packages (
for /D %%i in (site-packages/*) do IF "%%~xi" == "" (IF NOT EXIST Lib\site-packages\%%i (
    echo Move noarch package: %%i
    move site-packages\%%i Lib\site-packages
))
rmdir /S/Q site-packages
)

@echo on
REM Link installed plugins into Conda MicroDrop activated plugins directory.
call Scripts\activate.bat & python -m mpm.bin.api enable droplet_planning_plugin dmf_device_ui_plugin dropbot_plugin user_prompt_plugin step_label_plugin

REM Load plugins by default
call Scripts\activate.bat & microdrop-config edit --append plugins.enabled droplet_planning_plugin
call Scripts\activate.bat & microdrop-config edit --append plugins.enabled dmf_device_ui_plugin
call Scripts\activate.bat & microdrop-config edit --append plugins.enabled dropbot_plugin
call Scripts\activate.bat & microdrop-config edit --append plugins.enabled user_prompt_plugin
call Scripts\activate.bat & microdrop-config edit --append plugins.enabled step_label_plugin
