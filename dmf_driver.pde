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
#include "dmf_controller.h"

DmfController dmf_controller;

extern "C" {
  void PeakExceededWrapper() {
    dmf_controller.PeakExceeded();
  }
}

void setup() {
  dmf_controller.begin();
  Serial.print(dmf_controller.name());
  Serial.print(" v");
  Serial.println(dmf_controller.version());
  Serial.print("ram="); Serial.println(ram_size(), DEC);
  Serial.print(".data="); Serial.println(data_size(), DEC);
  Serial.print(".bss="); Serial.println(bss_size(), DEC);
  Serial.print("heap="); Serial.println(heap_size(), DEC);
  Serial.print("stack="); Serial.println(stack_size(), DEC);
  Serial.print("free memory="); Serial.println(free_memory(), DEC);
}

void loop() {
  dmf_controller.Listen();
}
