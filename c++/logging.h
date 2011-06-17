#ifndef _LOGGING_H
#define _LOGGING_H

#include <stdint.h>


class Logging {
public:
  static const uint8_t DEBUG=9;
  static const uint8_t INFO=6;
  static const uint8_t WARN=3;
  static const uint8_t ERROR=0;

  // display any log messages<=level (default is 9)
  static void SetLogLevel(uint8_t level) { log_level_ = level; }
  static void LogDebug(const char* message,
                       const char* class_name = 0,
                       const char* function_name = 0) {
                       LogMessage(Logging::DEBUG,
                                  message,class_name,function_name); }
  static void LogInfo(const char* message,
                       const char* class_name = 0,
                       const char* function_name = 0) {
                       LogMessage(Logging::INFO,
                                  message,class_name,function_name); }
  static void LogWarning(const char* message,
                         const char* class_name = 0,
                         const char* function_name = 0) {
                         LogMessage(Logging::WARN,
                                    message,class_name,function_name); }
  static void LogError(const char* message,
                       const char* class_name = 0,
                       const char* function_name = 0) {
                       LogMessage(Logging::ERROR,
                                  message,class_name,function_name); }
  static void LogMessage(uint8_t log_level,
                         const char* message,
                         const char* class_name = 0,
                         const char* function_name = 0);
  // log messages with formatting and a variable argument list
  static void LogMessageF(uint8_t log_level,
			  const char* message,
			  const char* class_name = 0,
			  const char* function_name = 0,
			  ... );
  static void LogSeparator(char s='=');

private:
  static void PrintClassAndFunction(const char* class_name,
                                    const char* function_name);
  static void Print(const char* str);
  static uint8_t log_level_;
};

#endif // _LOGGING_H
