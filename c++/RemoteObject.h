////////////////////////////////////////////////////////////////////////////////
//
// RemoteObject
//
// This class implements a simple communication protocol between a PC and
// Arduino over an RS-232 link using HDLC-like framing.  We use a wrapper
// for the boost asio library (SimpleSerial) that provides an interface that
// closely matches the Serial library on the Arduino.  This allows us to share
// the bulk of the code between the PC (Windows, Linux or Mac) and the Arduino.
//
// This implementation was partly inspired by Alvaro Lopes' serpro project:
//   https://github.com/alvieboy/arduino-serpro
//
// Each packet has the following structure:
//
//  +------------+---------+----------------+---------+------------+----------+
//  | Start Flag | Command | Payload Length | Payload |    CRC     | End Flag |
//  |   1 byte   | 1 byte  |    1-2 bytes   | N bytes |  2 bytes   |  1 byte  |
//  |    0x7E    |         |                |         | (optional) |   0x7E   |
//  +------------+---------+----------------+---------+------------+----------+
//
// The payload length can be one or two bytes.  If the payload is less than 128
// bytes, it's length is expressed as a single byte.  If the most-significant
// bit is set, the length is expressed as two bytes and can be recovered by
// clearing the most significant byte (i.e. PAYLOAD_LENGTH & 0x7FFF).
//
//   Examples:
//
//     payload length of 3, one byte: 0x04
//     payload length of 512, two bytes: 0x82 0x01
//
// Total packet length (not including flags) = Header Length (2-3 bytes)
//                                             + Payload Length
//                                             (+ 2 if CRC is enabled)
//
// To use this class, you must derive a class based on it and reimplement the
// virtual member function "ProcessPacket(...)".
//
////////////////////////////////////////////////////////////////////////////////

#ifndef _REMOTE_OBJECT_H
#define	_REMOTE_OBJECT_H

#include <stdint.h>

#ifndef AVR
  #include "logging.h"
  #include "SimpleSerial.h"
  #include <string>
#endif

class RemoteObject {
public:
#ifndef AVR
  static const uint32_t TIMEOUT_MICROSECONDS = 2000000; // TODO: this should be configurable
#endif

  // protocol constants
  static const uint16_t MAX_PAYLOAD_LENGTH =      2001;
  static const uint8_t MAX_STRING_SIZE =            80;

  // reserved commands
  static const uint8_t CMD_GET_PROTOCOL_NAME =    0x80;
  static const uint8_t CMD_GET_PROTOCOL_VERSION = 0x81;
  static const uint8_t CMD_GET_DEVICE_NAME =      0x82;
  static const uint8_t CMD_GET_MANUFACTURER =     0x83;
  static const uint8_t CMD_GET_HARDWARE_VERSION = 0x84;
  static const uint8_t CMD_GET_SOFTWARE_VERSION = 0x85;
  static const uint8_t CMD_GET_URL =              0x86;

  // reserved return codes
  static const uint8_t RETURN_OK =                0x00;
  static const uint8_t RETURN_GENERAL_ERROR =     0x01;
  static const uint8_t RETURN_UNKNOWN_COMMAND =   0x02;
  static const uint8_t RETURN_TIMEOUT =           0x03;
  static const uint8_t RETURN_NOT_CONNECTED =     0x04;
  static const uint8_t RETURN_BAD_INDEX =         0x05;
  static const uint8_t RETURN_BAD_PACKET_SIZE =   0x06;
  static const uint8_t RETURN_BAD_CRC =           0x07;

  RemoteObject(uint32_t baud_rate,
                 bool crc_enabled_
#ifndef AVR
                 ,const char* class_name
#endif
                 );
  ~RemoteObject();

  void set_debug(const bool debug);
  uint8_t return_code() {return return_code_; }
  bool crc_enabled() { return crc_enabled_; }

#ifdef AVR
  void Listen();
  // these methods force the derived class to define functions that
  // return the following attributes
  virtual const char* protocol_name() = 0;
  virtual const char* protocol_version() = 0;
  virtual const char* name() = 0;
  virtual const char* manufacturer() = 0;
  virtual const char* software_version() = 0;
  virtual const char* hardware_version() = 0;
  virtual const char* url() = 0;
#else
  // these methods query the remote device for protocol name/version
  virtual std::string protocol_name() = 0;
  virtual std::string protocol_version() = 0;
  virtual std::string name() = 0;
  virtual std::string manufacturer() = 0;
  virtual std::string software_version() = 0;
  virtual std::string hardware_version() = 0;
  virtual std::string url() = 0;

  bool connected() { return Serial.isOpen(); }  
  uint8_t Connect(const char* port);
#endif

protected:
  // these virtual methods must be overriden in the derived class
  virtual void ProcessCommand(uint8_t cmd) = 0;
  virtual void ProcessReply(uint8_t cmd) = 0;
  uint16_t payload_length() { return payload_length_; }

  // WARNING: The following two functions should only be used if you really
  // know what you are doing!  In most cases you can just use Serialize().
  uint8_t* payload() { return payload_; } // pointer to the payload buffer
  void bytes_written(uint16_t bytes) { bytes_written_+=bytes; }

  template<typename T>
    void Serialize(T data,uint16_t size) {
      Serialize((const uint8_t*)data,size); }
  void Serialize(const uint8_t* u, const uint16_t size);
  void SendReply(const uint8_t return_code);

  template<typename T> void ReadArray(T* array, const uint16_t size) {
#ifndef AVR
    LogMessage("","ReadArray()");
#endif
    bytes_read_ += size;
    memcpy(array,payload_+bytes_read_-size,size);
  }
  const char* ReadString();
  uint16_t ReadUint16();
  uint8_t ReadUint8();
  float ReadFloat();
  uint8_t WaitForReply();
  uint8_t SendCommand(const uint8_t cmd);

#ifndef AVR
  inline void LogMessage(const char* msg,
                         const char* function_name,
                         uint8_t level=5) {
          if(debug_) {
            Logging::LogMessage(level,msg,class_name_.c_str(),function_name); }}
  inline void LogError(const char* msg, const char* function_name) {
          if(debug_) {
          Logging::LogError(msg,class_name_.c_str(),function_name); }}
  inline void LogSeparator() { if(debug_) { Logging::LogSeparator(); }}
  static char log_message_string_[];
#endif
  uint8_t return_code_; // return code

private:
  static const uint8_t FRAME_BOUNDARY =           0x7E;
  static const uint8_t CONTROL_ESCAPE =           0x7D;
  static const uint8_t ESCAPE_XOR =               0x20;

  void SendPreamble();
  void SendPayload();
  void SendByte(uint8_t b);
  uint16_t UpdateCrc(uint16_t crc, uint8_t data);
  void ProcessPacket();
  void ProcessSerialInput(const uint8_t byte);

  uint8_t packet_cmd_; // command
  uint8_t payload_[MAX_PAYLOAD_LENGTH]; // payload
  uint16_t payload_length_; // length of the payload
  uint8_t header_length_; // length of the packet header (2 if payload is
                          // <128 bytes, 3 otherwise)
  uint32_t baud_rate_;
  uint16_t bytes_received_; // bytes received so far in packet
  uint16_t bytes_read_; // bytes that have been read (by Read methods)
  uint16_t bytes_written_; // bytes that have been written (by Serialize method)
  bool un_escaping_; // flag that the last byte was an escape
  bool waiting_for_reply_; // flag that we are waiting for a response
  bool crc_enabled_;
  uint16_t tx_crc_;
  uint16_t rx_crc_;
  bool debug_;
#ifndef AVR
  SimpleSerial Serial;
  std::string class_name_;
  boost::posix_time::ptime time_cmd_sent_;
#endif
};

#endif	// _REMOTE_OBJECT_H
