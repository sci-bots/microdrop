#include "RemoteObject.h"

#ifdef AVR
#include <util/crc16.h>
#include "WProgram.h"
extern "C" void __cxa_pure_virtual(void); // These declarations are needed for
void __cxa_pure_virtual(void) {}          // virtual functions on the Arduino.
#else
#include <boost/thread.hpp>
#include <boost/timer.hpp>
#include <boost/date_time/posix_time/posix_time_types.hpp>
using namespace std;

char RemoteObject::log_message_string_[MAX_STRING_SIZE];
#endif

RemoteObject::RemoteObject(uint32_t baud_rate,
                               bool crc_enabled
#ifndef AVR
                               ,const char* class_name //used for logging
#endif
                               ) : baud_rate_(baud_rate),
                                crc_enabled_(crc_enabled)
#ifndef AVR
                                ,class_name_(class_name)
#endif
                                {
  bytes_received_ = 0;
  un_escaping_ = false;
  payload_length_ = 0;
  bytes_read_ = 0;
  bytes_written_ = 0;
  debug_ = false;
}

RemoteObject::~RemoteObject() {
}

void RemoteObject::set_debug(const bool debug) {
  debug_ = debug;
}

void RemoteObject::SendByte(const uint8_t b) {
#ifndef AVR
  const char* function_name = "SendByte()";
#endif
  if(b==FRAME_BOUNDARY || b==CONTROL_ESCAPE) {
#ifndef AVR
    sprintf(log_message_string_,"write escape (0x%0X)",b);
    LogMessage(log_message_string_,function_name);
#endif
    Serial.write(CONTROL_ESCAPE);
    Serial.write(b^ESCAPE_XOR);
  } else {
#ifndef AVR
    sprintf(log_message_string_,"write (0x%0X)",b);
    LogMessage(log_message_string_,function_name);
#endif
    Serial.write(b);
  }
}

uint16_t RemoteObject::UpdateCrc(uint16_t crc, uint8_t data) {
#ifdef AVR
  crc = _crc16_update(crc,data);
#else
  crc ^= data;
  for(uint8_t i=0; i<8; i++) {
    if(crc & 1) {
      crc = (crc >> 1) ^ 0xA001;
    } else {
      crc = (crc >> 1);
    }
  }
#endif
  return crc;
}

void RemoteObject::SendPreamble() {
  payload_length_ = bytes_written_;
#ifndef AVR
  const char* function_name = "SendPreamble()";
  sprintf(log_message_string_,
          "command=0x%0X (%d), payload_length=%d",
          packet_cmd_,packet_cmd_,payload_length_);
  LogMessage(log_message_string_,function_name);
#endif
  Serial.write(FRAME_BOUNDARY);
  if(crc_enabled_) {
    tx_crc_ = 0xFFFF; // reset crc
    tx_crc_ = UpdateCrc(tx_crc_, packet_cmd_);
  }
  SendByte(packet_cmd_);
  if(payload_length_<128) {
    if(crc_enabled_) {
      tx_crc_ = UpdateCrc(tx_crc_, (uint8_t)payload_length_);
    }
    SendByte((uint8_t)payload_length_);
  } else {
    if(crc_enabled_) {
      tx_crc_ = UpdateCrc(tx_crc_, (uint8_t)((0x8000|payload_length_)>>8));
      tx_crc_ = UpdateCrc(tx_crc_, (uint8_t)payload_length_);
    }
    SendByte((uint8_t)((0x8000|payload_length_)>>8));
    SendByte((uint8_t)payload_length_);
  }
}

uint8_t RemoteObject::SendCommand(const uint8_t cmd) {
#ifndef AVR
  const char* function_name = "SendCommand()";
  LogSeparator();
  LogMessage("",function_name);
  time_cmd_sent_ = boost::posix_time::microsec_clock::universal_time();
#endif
  packet_cmd_ = cmd;
  SendPreamble();
  SendPayload();
  return_code_ = WaitForReply();
#ifndef AVR
  sprintf(log_message_string_,"return code=%d, cmd returned in %d us",
          return_code_, (boost::posix_time::microsec_clock::universal_time()
                         -time_cmd_sent_).total_microseconds());
  LogMessage(log_message_string_, function_name);
#endif
  return return_code_;
}

void RemoteObject::Serialize(const uint8_t* u,const uint16_t size) {
#ifndef AVR
  const char* function_name = "Serialize()";
  sprintf(log_message_string_,"%d bytes.",size);
  LogMessage(log_message_string_, function_name);
#endif
  //TODO check that MAX_PAYLOAD_LENGTH isn't exceeded
  for(uint16_t i=0;i<size;i++) {
#ifndef AVR
    sprintf(log_message_string_,"(0x%0X) byte %d",u[i],i);
    LogMessage(log_message_string_, function_name);
#endif
    payload_[bytes_written_+i]=u[i];
  }
  bytes_written_+=size;
}

void RemoteObject::SendPayload() {
#ifndef AVR
  const char* function_name = "SendPayload()";
  sprintf(log_message_string_,"%d bytes",payload_length_);
  LogMessage(log_message_string_, function_name);
#endif
  for(uint16_t i=0; i<payload_length_; i++) {
    if(crc_enabled_) {
      tx_crc_ = UpdateCrc(tx_crc_, payload_[i]);
    }
    SendByte(payload_[i]);
  }
  if(crc_enabled_) {
    SendByte((uint8_t)tx_crc_);
    SendByte((uint8_t)(tx_crc_>>8));
  }
  payload_length_ = 0;
  bytes_written_ = 0;
}

void RemoteObject::SendReply(uint8_t return_code) {
  Serialize(&return_code,1);
  SendPreamble();
  SendPayload();
}

const char* RemoteObject::ReadString() {
  const char* function_name = "ReadString()";
  // TODO check that we're not reading past the end of the buffer
  uint8_t length = strlen((const char*)payload_)+1;
  bytes_read_ += length;
#ifndef AVR
  sprintf(log_message_string_,
          "=\"%s\", bytes_read_=%d",
          (const char*)(payload_+bytes_read_-length),
          bytes_read_);
  LogMessage(log_message_string_, function_name);
#endif
  return (const char*)(payload_+bytes_read_-length);
}

uint8_t RemoteObject::ReadUint8() {
  bytes_read_ += sizeof(uint8_t);
#ifndef AVR
  const char* function_name = "ReadUint8()";
  sprintf(log_message_string_,
          "=%d, bytes_read_=%d",
          *(uint8_t*)(payload_+bytes_read_-sizeof(uint8_t)),
          bytes_read_);
  LogMessage(log_message_string_, function_name);
#endif
  return *(uint8_t*)(payload_+bytes_read_-sizeof(uint8_t));
}

uint16_t RemoteObject::ReadUint16() {
  bytes_read_ += sizeof(uint16_t);
#ifndef AVR
  const char* function_name = "ReadUint16()";
  sprintf(log_message_string_,
          "=%d, bytes_read_=%d",
          *(uint16_t*)(payload_+bytes_read_-sizeof(uint16_t)),
          bytes_read_);
  LogMessage(log_message_string_, function_name);
#endif
  return *(uint16_t*)(payload_+bytes_read_-sizeof(uint16_t));
}

float RemoteObject::ReadFloat() {
  bytes_read_ += sizeof(float);
#ifndef AVR
  const char* function_name = "ReadFloat()";
  sprintf(log_message_string_,
          "=%.1f, bytes_read_=%d",
          *(float*)(payload_+bytes_read_-sizeof(float)),
          bytes_read_);
  LogMessage(log_message_string_, function_name);
#endif
  return *(float*)(payload_+bytes_read_-sizeof(float));
}

uint8_t RemoteObject::WaitForReply() {
#ifndef AVR
  LogMessage("", "WaitForReply()");
#endif
  char b;
  waiting_for_reply_ = true;
  while(waiting_for_reply_) {
    if(Serial.available()) {
      b = Serial.read();
      ProcessSerialInput(b);
    }
#ifndef AVR
      else if((boost::posix_time::microsec_clock::universal_time()
       -time_cmd_sent_).total_microseconds()>TIMEOUT_MICROSECONDS) {
      return_code_ = RETURN_TIMEOUT;
      waiting_for_reply_ = false;
    }
#endif
  }
  return return_code_;
}

void RemoteObject::ProcessPacket() {
  if(packet_cmd_&0x80) { // Commands have MSB==1
    packet_cmd_ = packet_cmd_^0x80; // Flip the MSB for reply
    ProcessCommand(packet_cmd_^0x80);
#ifndef AVR
    LogSeparator();
#endif
  } else {
    return_code_ = payload_[payload_length_-1];
    payload_length_--;// -1 because we've already read the return code
    ProcessReply(packet_cmd_);
#ifndef AVR
    LogSeparator();
#endif
  }
}

void RemoteObject::ProcessSerialInput(uint8_t b) {
#ifndef AVR
  const char* function_name = "ProcessSerialInput()";
#endif
  // deal with escapes
  if (b==CONTROL_ESCAPE) {
#ifndef AVR
    sprintf(log_message_string_,"(0x%0X) Escape",b);
    LogMessage("", function_name);
#endif
    un_escaping_ = true;
    return;
  } else if(un_escaping_) {
    b^=ESCAPE_XOR;
#ifndef AVR
    sprintf(log_message_string_,
            "(0x%0X) Un-escaping",b);
    LogMessage(log_message_string_, function_name);
#endif
  }
  if (b==FRAME_BOUNDARY && !un_escaping_) {
#ifndef AVR
    LogSeparator();
    sprintf(log_message_string_,
            "(0x%0X) Frame Boundary",b);
    LogMessage(log_message_string_, function_name);
#endif
    if(bytes_received_>0) {
#ifndef AVR
      sprintf(log_message_string_,"(0x%0X) Invalid packet",b);
      LogMessage(log_message_string_, function_name);
#endif
    }
    bytes_received_ = 0;
  } else {
    if(bytes_received_==0) { // command byte
#ifndef AVR
      sprintf(log_message_string_,
              "(0x%0X) Command byte (%d)",b,b);
      LogMessage(log_message_string_, function_name);
#endif
      packet_cmd_=b;
      if(crc_enabled_) {
        rx_crc_=0xFFFF; // reset the crc
      }
    } else if(bytes_received_==1) { // payload length
      if(b & 0x80) {
        header_length_=3;
        payload_length_=(b&0x7F)<<8;
      } else {
        header_length_=2;
        payload_length_=b;
      }
    // payload length (byte 2)
    } else if(bytes_received_==2 && header_length_==3) {
      payload_length_+=b;
    } else if(bytes_received_-header_length_<payload_length_) { // payload
      // TODO: check that MAX_PAYLOAD_LENGTH isn't exceeded
      payload_[bytes_received_-header_length_]=b;
    } else if(bytes_received_-header_length_<payload_length_+2) { // crc
    } else {
      // TODO: error
    }
#ifndef AVR
    if(bytes_received_==header_length_) {
      sprintf(log_message_string_, "Payload length=%d", payload_length_);
      LogMessage(log_message_string_, function_name);
    }
#endif
    if(crc_enabled_) {
      rx_crc_ = UpdateCrc(rx_crc_, b);
    }
    bytes_received_++;
#ifndef AVR
    if(b>=0x20&&b<=0x7E) {
      sprintf(log_message_string_,
              "(0x%0X) %d bytes received (\'%c\')",
              b, bytes_received_ ,b);
    } else {
      sprintf(log_message_string_,
              "(0x%0X) %d bytes received",
              b, bytes_received_);
    }
    LogMessage(log_message_string_, function_name);
#endif
    if(bytes_received_==payload_length_+header_length_+2*crc_enabled_) {
      waiting_for_reply_ = false;
      bytes_received_ = 0;
      bytes_read_ = 0;
      bytes_written_ = 0;
#ifndef AVR
      if(crc_enabled_) {
        if(rx_crc_==0) {
          LogMessage("End of Packet. CRC OK.", function_name);
        } else {
          LogMessage("End of Packet. CRC Error.", function_name);
        }
      } else {
        LogMessage("End of Packet", function_name);
      }
      LogSeparator();
#endif
      ProcessPacket();
    }
  }
  if(un_escaping_) {
    un_escaping_=false;

  }
}

#ifdef AVR
////////////////////////////////////////////////////////////////////////////////
//
// These functions are only defined on the Arduino
//
////////////////////////////////////////////////////////////////////////////////

void RemoteObject::Listen() {
  while(Serial.available()>0) {
    ProcessSerialInput(Serial.read());
  }
}
#else
////////////////////////////////////////////////////////////////////////////////
//
// These functions are only defined on the PC
//
////////////////////////////////////////////////////////////////////////////////

uint8_t RemoteObject::Connect(const char* port) {
  const char* function_name = "Connect()";
  int return_code = Serial.begin(port, baud_rate_);
  sprintf(log_message_string_,"Serial.begin(%s,%d)=%d",
          port,baud_rate_,return_code);
  LogMessage(log_message_string_, function_name);
  if(return_code==0) {
    LogMessage("Sleep for 2 second so the Arduino can get ready.",
               function_name);
    boost::this_thread::sleep(boost::posix_time::milliseconds(2000));
  }
  return return_code;
}

#endif
