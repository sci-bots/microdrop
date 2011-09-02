/*
  Driver for Arduino DMF controller

  Ryan Fobel and Andrei Vovk, 2009-10
  ryan@fobel.net
  andrei.vovk@utoronto.ca
*/

#include <Memory.h>
#include <RemoteObject.h>
#include <Wire.h>
#include <SPI.h>
#include "dmf_control_board.h"

DmfControlBoard dmf_control_board;

extern "C" {
  void PeakExceededWrapper() {
    dmf_control_board.PeakExceeded();
  }
}

void setup() {
  dmf_control_board.begin();
  Serial.print(dmf_control_board.name());
  Serial.print(" v");
  Serial.println(dmf_control_board.software_version());
  Serial.print("ram="); Serial.println(ram_size(), DEC);
  Serial.print(".data="); Serial.println(data_size(), DEC);
  Serial.print(".bss="); Serial.println(bss_size(), DEC);
  Serial.print("heap="); Serial.println(heap_size(), DEC);
  Serial.print("stack="); Serial.println(stack_size(), DEC);
  Serial.print("free memory="); Serial.println(free_memory(), DEC);
}

void loop() {
  dmf_control_board.Listen();
}
