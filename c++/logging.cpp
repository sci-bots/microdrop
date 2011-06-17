#include <string.h>
#include "logging.h"

#include <iostream>
#include <stdio.h>
#include <cstdarg>
using namespace std;

uint8_t Logging::log_level_ = Logging::DEBUG;

void Logging::LogMessage(uint8_t log_level,
                         const char* message,
                         const char* class_name,
                         const char* function_name) {
  if(log_level<=log_level_) {
    PrintClassAndFunction(class_name,function_name);
    Print(message);
    Print("\r\n");
  }
}

/**
 * Log a message with formatting and a variable argument list.
 * \param log_level message priority
 * \param message the format of the message (same as printf)
 */
void Logging::LogMessageF(uint8_t log_level,
			  const char* message,
			  const char* class_name,
			  const char* function_name,
			  ... ) {
  if(log_level<=log_level_) {
    PrintClassAndFunction(class_name,function_name);
    va_list argList;
    va_start(argList, message);
    vprintf(message, argList);
    va_end(argList);
    Print("\r\n");
  }
}

void Logging::LogSeparator(char s) {
  char separator[81];
  memset(separator,s,80);
  separator[80] = 0;
  Print(separator);
  Print("\r\n");
}

void Logging::PrintClassAndFunction(const char* class_name,
                                  const char* function_name) {
  if(class_name) {
    Print(class_name);
  }
  if(class_name&&function_name) {
    Print("::");
  }
  if(function_name) {
    Print(function_name);
  }
  if(class_name||function_name) {
    Print(": ");
  }
}

void Logging::Print(const char* str) {
  cout<<str<<flush;
}
