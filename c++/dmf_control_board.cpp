#include <stdint.h>
#include "dmf_control_board.h"

#ifndef AVR
using namespace std;
#include <boost/date_time/posix_time/posix_time_types.hpp>
#else
#include "WProgram.h"
#include <Wire.h>
#include <SPI.h>
#include <math.h>
#endif

#ifdef AVR
extern "C" {
  void PeakExceededWrapper();
}

const float DmfControlBoard::CH0_SERIES_RESISTORS_[] = {1e5, 1e6};
const float DmfControlBoard::CH1_SERIES_RESISTORS_[] = {1e3, 1e4, 1e5, 1e6};
const float DmfControlBoard::SAMPLING_RATES_[] = { 8908, 16611, 29253, 47458,
                                                 68191, 90293, 105263 };
const char DmfControlBoard::PROTOCOL_NAME_[] = "DMF Control Protocol";
const char DmfControlBoard::PROTOCOL_VERSION_[] = "0.1";
const char DmfControlBoard::NAME_[] = "Arduino DMF Controller";
const char DmfControlBoard::VERSION_[] = "1.1";
#else
const char DmfControlBoard::CSV_INDENT_[] = ",,,,,,,,";
#endif

DmfControlBoard::DmfControlBoard()
  : RemoteObject(BAUD_RATE,true
#ifndef AVR
                   ,"DmfControlBoard" //used for logging
#endif
                   ) {
}

DmfControlBoard::~DmfControlBoard() {
}

void DmfControlBoard::ProcessCommand(uint8_t cmd) {
#ifndef AVR
  const char* function_name = "ProcessCommand()";
  sprintf(log_message_string_,"command=0x%0X (%d)",
          cmd,cmd);
  LogMessage(log_message_string_, function_name);
#endif
  uint8_t return_code = RETURN_UNKNOWN_COMMAND;
  switch(cmd) {
#ifdef AVR // Commands that only the Arduino handles
    case CMD_GET_PROTOCOL_NAME:
      if(payload_length()==0) {
        Serialize(PROTOCOL_NAME_,sizeof(PROTOCOL_NAME_));
        return_code = RETURN_OK;
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_GET_PROTOCOL_VERSION:
      if(payload_length()==0) {
        Serialize(PROTOCOL_VERSION_,sizeof(PROTOCOL_VERSION_));
        return_code = RETURN_OK;
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_GET_DEVICE_NAME:
      if(payload_length()==0) {
        Serialize(NAME_,sizeof(NAME_));
        return_code = RETURN_OK;
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_GET_DEVICE_VERSION:
      if(payload_length()==0) {
        Serialize(VERSION_,sizeof(VERSION_));
        return_code = RETURN_OK;
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_GET_NUMBER_OF_ELECTRODES:
      if(payload_length()==0) {
        uint16_t n = NUMBER_OF_ELECTRODES_;
        Serialize(&n,sizeof(n));
        return_code = RETURN_OK;
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_GET_STATE_OF_ALL_ELECTRODES:
      if(payload_length()==0) {
        Serialize(state_of_electrodes_,NUMBER_OF_ELECTRODES_*sizeof(uint8_t));
        return_code = RETURN_OK;
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_SET_STATE_OF_ALL_ELECTRODES:
      if(payload_length()==NUMBER_OF_ELECTRODES_*sizeof(uint8_t)) {
        ReadArray(state_of_electrodes_,
                  NUMBER_OF_ELECTRODES_*sizeof(uint8_t));
        UpdateAllElectrodes();
        return_code = RETURN_OK;
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_GET_STATE_OF_ELECTRODE:
      if(payload_length()==sizeof(uint16_t)) {
        uint16_t electrode = ReadUint16();
        if(electrode>=NUMBER_OF_ELECTRODES_||electrode<0) {
          return_code = RETURN_BAD_INDEX;
        } else {
          Serialize(&electrode,sizeof(electrode));
          Serialize(&state_of_electrodes_[electrode],
                    sizeof(state_of_electrodes_[electrode]));
          return_code = RETURN_OK;
        }
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_SET_STATE_OF_ELECTRODE:
      if(payload_length()==sizeof(uint16_t)+sizeof(uint8_t)) {
        uint16_t electrode = ReadUint16();
        if(electrode<NUMBER_OF_ELECTRODES_) {
          state_of_electrodes_[electrode] = ReadUint8();
          UpdateElectrode(electrode);
          return_code = RETURN_OK;
        } else {
          return_code = RETURN_BAD_INDEX;
        }
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_GET_ACTUATION_WAVEFORM:
      //TODO
      break;
    case CMD_SET_ACTUATION_WAVEFORM:
      //TODO
      break;
    case CMD_GET_ACTUATION_VOLTAGE:
      //TODO
      break;
    case CMD_SET_ACTUATION_VOLTAGE:
      if(payload_length()==sizeof(uint8_t)) {
        uint8_t voltage = ReadUint8();
          SendSPI(AD5204_SLAVE_SELECT_PIN_,4,voltage);
          return_code = RETURN_OK;
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_GET_ACTUATION_FREQUENCY:
      //TODO
      break;
    case CMD_SET_ACTUATION_FREQUENCY:
      if(payload_length()==sizeof(float)) {
        float freq = ReadFloat();
        // valid frequencies are 1kHz to 68MHz
        if(freq<1e3 || freq>68e6) {
          return_code = RETURN_GENERAL_ERROR;
        } else {
          uint8_t oct = 3.322*log(freq/1039)/log(10);
          uint16_t dac = round(2048-(2078*(float)(1<<(10+oct)))/freq);
          uint8_t cnf = 2; // CLK on, /CLK off
          // msb = OCT3 OCT2 OCT1 OCT0 DAC9 DAC8 DAC7 DAC6
          uint8_t msb = (oct << 4) | (dac >> 6);
          // lsb =  DAC5 DAC4 DAC3 DAC2 DAC1 DAC0 CNF1 CNF0
          uint8_t lsb = (dac << 2) | cnf;
          Wire.beginTransmission(LTC6904_);
          Wire.send(msb);
          Wire.send(lsb);
          Wire.endTransmission();     // stop transmitting
          return_code = RETURN_OK;
        }
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_GET_SAMPLING_RATE:
      if(payload_length()==0) {
        Serialize(&SAMPLING_RATES_[sampling_rate_index_],sizeof(float));
        return_code = RETURN_OK;
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_SET_SAMPLING_RATE:
      if(payload_length()==sizeof(uint8_t)) {
        return_code = SetAdcPrescaler(ReadUint8());
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_GET_SERIES_RESISTOR:
      if(payload_length()==sizeof(uint8_t)) {
        uint8_t channel = ReadUint8();
        return_code = RETURN_OK;
        switch(channel) {
          case 0:
            Serialize(&CH0_SERIES_RESISTORS_[ch0_series_resistor_index_],
                      sizeof(float));
            break;
          case 1:
            Serialize(&CH1_SERIES_RESISTORS_[ch1_series_resistor_index_],
                      sizeof(float));
            break;
          default:
            return_code = RETURN_BAD_INDEX;
            break;
        }
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_SET_SERIES_RESISTOR:
      if(payload_length()==2*sizeof(uint8_t)) {
        uint8_t channel = ReadUint8();
        return_code = SetSeriesResistor(channel, ReadUint8());
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_SET_POT:
      if(payload_length()==2*sizeof(uint8_t)) {
        uint8_t index = ReadUint8();
        return_code = SetPot(index, ReadUint8());
      } else {
        return_code = RETURN_BAD_PACKET_SIZE;
      }
      break;
    case CMD_SAMPLE_VOLTAGE:
      if(payload_length()<2*sizeof(uint8_t)+3*sizeof(uint16_t)) {
        return_code = RETURN_BAD_PACKET_SIZE;
      } else {
        uint16_t n_samples = ReadUint16();
        uint16_t n_sets = ReadUint16();
        uint16_t delay_between_sets_ms = ReadUint16();
        uint16_t n_channels = ReadUint8();
        if(n_samples*n_sets*n_channels>MAX_SAMPLES) {
          return_code = RETURN_GENERAL_ERROR;
        } else {
          if((payload_length()==sizeof(uint8_t)+3*sizeof(uint16_t)
             +n_channels*sizeof(uint8_t))
             || (payload_length()==sizeof(uint8_t)+3*sizeof(uint16_t)
             +n_channels*sizeof(uint8_t)
             +NUMBER_OF_ELECTRODES_*sizeof(uint8_t))) {
            return_code = RETURN_OK;

            // point the voltage_buffer_ to the payload_buffer_
            uint16_t* voltage_buffer_ = (uint16_t*)payload();
            // update the number of bytes written
            bytes_written(n_sets*n_samples*n_channels*sizeof(uint16_t));

            uint8_t channel[NUMBER_OF_AD_CHANNELS];
            for(uint8_t i=0; i<n_channels; i++) {
              channel[i] = ReadUint8();
            }
            // update the electrodes (if they were included in the packet)
            if(payload_length()==sizeof(uint8_t)+3*sizeof(uint16_t)
               +n_channels*sizeof(uint8_t)
               +NUMBER_OF_ELECTRODES_*sizeof(uint8_t)){
              ReadArray(state_of_electrodes_,
                        NUMBER_OF_ELECTRODES_*sizeof(uint8_t));
              UpdateAllElectrodes();
            }
            // sample the voltages
            for(uint16_t i=0; i<n_sets; i++) {
              // dummy read to let the adc settle
              analogRead(channel[0]);
              for(uint16_t j=0; j<n_samples; j++) {
                for(uint16_t k=0; k<n_channels; k++) {
                  voltage_buffer_[i*n_samples*n_channels+j*n_channels+k] =
                    analogRead(channel[k]);
                }
              }
              uint32_t t = millis();
              while(millis()-t<delay_between_sets_ms) {
              }
            }
          } else {
            return_code = RETURN_BAD_PACKET_SIZE;
          }
        }
      }
      break;
    case CMD_MEASURE_IMPEDANCE:
      if(payload_length()<3*sizeof(uint16_t)) {
        return_code = RETURN_BAD_PACKET_SIZE;
      } else {
        uint16_t sampling_time_ms = ReadUint16();
        uint16_t n_sets = ReadUint16();
        uint16_t delay_between_sets_ms = ReadUint16();

        if(n_sets*2>MAX_SAMPLES) {
          return_code = RETURN_GENERAL_ERROR;
        } else {
          if(payload_length()==3*sizeof(uint16_t) ||
             (payload_length()==3*sizeof(uint16_t)
             +NUMBER_OF_ELECTRODES_*sizeof(uint8_t))) {
            return_code = RETURN_OK;

            // point the impedance_buffer_ to the payload_buffer_
            uint16_t* impedance_buffer_ = (uint16_t*)payload();

            // update the number of bytes written
            bytes_written(n_sets*2*sizeof(uint16_t));

            // update the electrodes (if they were included in the packet)
            if(payload_length()==3*sizeof(uint16_t)
               +NUMBER_OF_ELECTRODES_*sizeof(uint8_t)){
              ReadArray(state_of_electrodes_,
                        NUMBER_OF_ELECTRODES_*sizeof(uint8_t));
              UpdateAllElectrodes();
            }

            // sample the impedance
            for(uint16_t i=0; i<n_sets; i++) {
              uint16_t hv_peak = 0;
              uint16_t hv = 0;
              uint16_t fb_peak = 0;
              uint16_t fb = 0;
              uint32_t t = millis();
              while(millis()-t<sampling_time_ms) {
                hv = analogRead(0);
                if(hv>hv_peak) {
                    hv_peak = hv;
                }
                fb = analogRead(1);
                if(fb>fb_peak) {
                    fb_peak = fb;
                }
              }

              impedance_buffer_[2*i] = hv_peak;
              impedance_buffer_[2*i+1] = fb_peak;

              while(millis()-t<delay_between_sets_ms) {
              }
            }
          } else {
            return_code = RETURN_BAD_PACKET_SIZE;
          }
        }
      }
      break;
#endif
    default:
#ifndef AVR
      LogError("Unrecognized command", function_name);
#endif
      break;
  }
  SendReply(return_code);
}

void DmfControlBoard::ProcessReply(uint8_t cmd) {
  uint8_t reply_to = cmd^0x80;
#ifndef AVR
  const char* function_name = "ProcessReply()";
  sprintf(log_message_string_,
          "(0x%0X). This packet is a reply to command (%d)",
          reply_to,reply_to);
  LogMessage(log_message_string_, function_name);
  sprintf(log_message_string_,"Return code=%d",return_code());
  LogMessage(log_message_string_, function_name);
  sprintf(log_message_string_,"Payload length=%d",payload_length());
  LogMessage(log_message_string_, function_name);
#endif
  if(return_code()==RETURN_OK) {
#ifndef AVR // Replies that only the PC handles
    switch(reply_to) {
      case CMD_GET_PROTOCOL_NAME:
        LogMessage("CMD_GET_PROTOCOL_NAME", function_name);
        protocol_name_ = ReadString();
        sprintf(log_message_string_,
                "protocol_name_=%s",
                protocol_name_.c_str());
        LogMessage(log_message_string_, function_name);
        break;
      case CMD_GET_PROTOCOL_VERSION:
        LogMessage("CMD_GET_PROTOCOL_VERSION", function_name);
        protocol_version_ = ReadString();
        sprintf(log_message_string_,
                "protocol_version_=%s",
                protocol_version_.c_str());
        LogMessage(log_message_string_, function_name);
        break;
      case CMD_GET_DEVICE_NAME:
        LogMessage("CMD_GET_DEVICE_NAME", function_name);
        name_ = ReadString();
        sprintf(log_message_string_,
                "name_=%s",
                name_.c_str());
        LogMessage(log_message_string_, function_name);
        break;
      case CMD_GET_DEVICE_VERSION:
        LogMessage("CMD_GET_DEVICE_VERSION", function_name);
        version_ = ReadString();
        sprintf(log_message_string_,
                "version_=%s",
                version_.c_str());
        LogMessage(log_message_string_, function_name);
        break;
      case CMD_GET_NUMBER_OF_ELECTRODES:
        LogMessage("CMD_GET_DEVICE_VERSION", function_name);
        if(payload_length()==sizeof(uint16_t)) {
          state_of_electrodes_.resize(ReadUint16());
          sprintf(log_message_string_,
                  "state_of_electrodes_.size()=%d",
                  state_of_electrodes_.size());
          LogMessage(log_message_string_, function_name);
        } else {
          LogMessage("CMD_GET_NUMBER_OF_ELECTRODES, Bad packet size",
                     function_name);
        }
        break;
      case CMD_GET_STATE_OF_ALL_ELECTRODES:
        LogMessage("CMD_GET_STATE_OF_ALL_ELECTRODES", function_name);
        state_of_electrodes_.clear();
        for(int i=0; i<payload_length(); i++) {
          state_of_electrodes_.push_back(ReadUint8());
          sprintf(log_message_string_,
                  "state_of_electrodes_[%d]=%d",
                  i,state_of_electrodes_[i]);
          LogMessage(log_message_string_, function_name);
        }
        break;
      case CMD_SET_STATE_OF_ALL_ELECTRODES:
        LogMessage("CMD_SET_STATE_OF_ALL_ELECTRODES", function_name);
        LogMessage("all electrodes set successfully", function_name);
        break;
      case CMD_GET_STATE_OF_ELECTRODE:
        LogMessage("CMD_GET_STATE_OF_ELECTRODE", function_name);
        if(payload_length()==sizeof(uint16_t)+sizeof(uint8_t)) {
          uint16_t electrode = ReadUint16();
          if(electrode+1>state_of_electrodes_.size()) {
            state_of_electrodes_.resize(electrode+1);
          }
          state_of_electrodes_[electrode]=ReadUint8();
          sprintf(log_message_string_,
                "electrode[%d]=%d",
                electrode,state_of_electrodes_[electrode]);
          LogMessage(log_message_string_, function_name);
        } else {
            LogError("Bad packet size", function_name);
        }
        break;
      case CMD_SET_STATE_OF_ELECTRODE:
        LogMessage("CMD_SET_STATE_OF_ELECTRODE", function_name);
        LogMessage("electrode set successfully", function_name);
        break;
      case CMD_SET_ACTUATION_VOLTAGE:
      {
        LogMessage("CMD_SET_ACTUATION_VOLTAGE", function_name);
        LogMessage("volage set successfully", function_name);
        break;
      }
      case CMD_SET_ACTUATION_FREQUENCY:
      {
        LogMessage("CMD_SET_ACTUATION_FREQUENCY", function_name);
        LogMessage("frequency set successfully", function_name);
        break;
      }
      case CMD_GET_SAMPLING_RATE:
      {
        LogMessage("CMD_GET_SAMPLING_RATE", function_name);
        if(payload_length()==sizeof(float)) {
          sampling_rate_ = ReadFloat();
          sprintf(log_message_string_,
                  "sampling_rate_=%.1e",sampling_rate_);
          LogMessage(log_message_string_, function_name);
        } else {
          return_code_ = RETURN_BAD_PACKET_SIZE;
          LogMessage("CMD_GET_SAMPLING_RATE, Bad packet size",
                     function_name);
        }
        break;
      }
      case CMD_SET_SAMPLING_RATE:
      {
        LogMessage("CMD_SET_SAMPLING_RATE", function_name);
        LogMessage("sampling rate set successfully", function_name);
        break;
      }
      case CMD_GET_SERIES_RESISTOR:
      {
        LogMessage("CMD_GET_SERIES_RESISTOR", function_name);
        if(payload_length()==sizeof(float)) {
          series_resistor_ = ReadFloat();
          sprintf(log_message_string_,
                  "series_resistor_=%.1e",series_resistor_);
          LogMessage(log_message_string_, function_name);
        } else {
          return_code_ = RETURN_BAD_PACKET_SIZE;
          LogMessage("CMD_GET_SERIES_RESISTOR, Bad packet size",
                     function_name);
        }
        break;
      }
      case CMD_SET_SERIES_RESISTOR:
      {
        LogMessage("CMD_SET_SERIES_RESISTOR", function_name);
        LogMessage("series resistor set successfully", function_name);
        break;
      }
      case CMD_SET_POT:
      {
        LogMessage("CMD_SET_POT", function_name);
        LogMessage("potentiometer set successfully", function_name);
        break;
      }
      case CMD_SAMPLE_VOLTAGE:
      {
        LogMessage("CMD_SAMPLE_VOLTAGE", function_name);
        uint16_t n_samples = payload_length()/sizeof(uint16_t);
        sprintf(log_message_string_,"Read %d feedback samples",n_samples);
        LogMessage(log_message_string_,function_name);
        voltage_buffer_.resize(n_samples);
        for(uint16_t i=0; i<n_samples; i++) {
          voltage_buffer_[i] = ReadUint16();
        }
        break;
      }
      case CMD_MEASURE_IMPEDANCE:
      {
        LogMessage("CMD_MEASURE_IMPEDANCE", function_name);
        uint16_t n_samples = payload_length()/2/sizeof(uint16_t);
        sprintf(log_message_string_,"Read %d impedance samples",n_samples);
        LogMessage(log_message_string_,function_name);
        impedance_buffer_.resize(2*n_samples);
        for(uint16_t i=0; i<2*n_samples; i++) {
          impedance_buffer_[i] = ReadUint16();
        }
        break;
      }
      default:
        LogError("Unrecognized command", function_name);
        break;
    }
#endif
  } else {
#ifndef AVR
    sprintf(log_message_string_,"return code=%d",
            return_code());
    LogError(log_message_string_, function_name);
#endif
  }
}

#ifdef AVR
////////////////////////////////////////////////////////////////////////////////
//
// These functions are only defined on the Arduino.
//
////////////////////////////////////////////////////////////////////////////////

void DmfControlBoard::begin() {
  analogReference(EXTERNAL);

  pinMode(AD5204_SLAVE_SELECT_PIN_, OUTPUT);
  pinMode(CH0_SERIES_RESISTOR_0_, OUTPUT);
  pinMode(CH1_SERIES_RESISTOR_0_, OUTPUT);
  pinMode(CH1_SERIES_RESISTOR_1_, OUTPUT);
  pinMode(CH1_SERIES_RESISTOR_2_, OUTPUT);

  Wire.begin();
  SPI.begin();

  // set PCA0505 ports in output mode
  for(uint8_t chip=0; chip<NUMBER_OF_ELECTRODES_/40; chip++) {
    for(uint8_t port=0; port<5; port++) {
      SendI2C(PCA9505_ADDRESS_+chip, PCA9505_CONFIG_IO_REGISTER_+port, 0x00);
    }
  }

  // set all electrodes to ground
  UpdateAllElectrodes();

  // set all potentiometers
  SetPot(POT_AREF,255);
  SetPot(POT_VGND,124);
  SetPot(POT_WAVEOUT_GAIN_1,128);
  SetPot(POT_WAVEOUT_GAIN_2,128);

  Serial.begin(DmfControlBoard::BAUD_RATE);
  SetSeriesResistor(0,0);
  SetSeriesResistor(1,0);
  SetAdcPrescaler(4);
}

void DmfControlBoard::PeakExceeded() {
  peak_++;
  SetPot(POT_AREF,peak_);
}

// send a command and some data to one of the I2C chips
// (code based on http://gdallaire.net/blog/?p=18)
void DmfControlBoard::SendI2C(uint8_t row, uint8_t cmd, uint8_t data) {
  Wire.beginTransmission(row);
  Wire.send(cmd);
  Wire.send(data);
  Wire.endTransmission();
}

void DmfControlBoard::SendSPI(uint8_t pin, uint8_t address, uint8_t data) {
  digitalWrite(pin,LOW);
  SPI.transfer(address);
  SPI.transfer(data);
  digitalWrite(pin,HIGH);
}

uint8_t DmfControlBoard::SetPot(uint8_t index, uint8_t value) {
  if(index>=0 && index<4) {
    SendSPI(AD5204_SLAVE_SELECT_PIN_, index, 255-value);
    return RETURN_OK;
  }
  return RETURN_BAD_INDEX;
}

uint8_t DmfControlBoard::SetAdcPrescaler(const uint8_t index) {
  uint8_t return_code = RETURN_OK;
  switch(128>>index) {
    case 128:
      ADCSRA |= _BV(ADPS2) | _BV(ADPS1) | _BV(ADPS0);
      break;
    case 64:
      ADCSRA |= _BV(ADPS2) | _BV(ADPS1);
      ADCSRA &= ~(_BV(ADPS0));
      break;
    case 32:
      ADCSRA |= _BV(ADPS2) | _BV(ADPS0);
      ADCSRA &= ~_BV(ADPS1);
      break;
    case 16:
      ADCSRA |= _BV(ADPS2);
      ADCSRA &= ~(_BV(ADPS1) | _BV(ADPS0));
      break;
    case 8:
      ADCSRA |= _BV(ADPS1) | _BV(ADPS0);
      ADCSRA &= ~_BV(ADPS2);
      break;
    case 4:
      ADCSRA |= _BV(ADPS1);
      ADCSRA &= ~(_BV(ADPS2) | _BV(ADPS0));
      break;
    case 2:
      ADCSRA |= _BV(ADPS0);
      ADCSRA &= ~(_BV(ADPS2) | _BV(ADPS1));
      break;
    default:
      return_code = RETURN_GENERAL_ERROR;
      break;
  }
  if(return_code==RETURN_OK){
    sampling_rate_index_ = index;
  }
  return return_code;
}


uint8_t DmfControlBoard::SetSeriesResistor(const uint8_t channel,
                                         const uint8_t index) {
  uint8_t return_code = RETURN_OK;
  if(channel==0) {
    switch(index) {
      case 0:
        digitalWrite(CH0_SERIES_RESISTOR_0_, HIGH);
        break;
      case 1:
        digitalWrite(CH0_SERIES_RESISTOR_0_, LOW);
        break;
      default:
        return_code = RETURN_BAD_INDEX;
        break;
    }
    if(return_code==RETURN_OK) {
      ch0_series_resistor_index_ = index;
    }
  } else if(channel==1) {
    switch(index) {
      case 0:
        digitalWrite(CH1_SERIES_RESISTOR_0_, HIGH);
        digitalWrite(CH1_SERIES_RESISTOR_1_, LOW);
        digitalWrite(CH1_SERIES_RESISTOR_2_, LOW);
        break;
      case 1:
        digitalWrite(CH1_SERIES_RESISTOR_0_, LOW);
        digitalWrite(CH1_SERIES_RESISTOR_1_, HIGH);
        digitalWrite(CH1_SERIES_RESISTOR_2_, LOW);
        break;
      case 2:
        digitalWrite(CH1_SERIES_RESISTOR_0_, LOW);
        digitalWrite(CH1_SERIES_RESISTOR_1_, LOW);
        digitalWrite(CH1_SERIES_RESISTOR_2_, HIGH);
        break;
      case 3:
        digitalWrite(CH1_SERIES_RESISTOR_0_, LOW);
        digitalWrite(CH1_SERIES_RESISTOR_1_, LOW);
        digitalWrite(CH1_SERIES_RESISTOR_2_, LOW);
        break;
      default:
        return_code = RETURN_BAD_INDEX;
        break;
    }
    if(return_code==RETURN_OK) {
      ch1_series_resistor_index_ = index;
    }
  } else { // bad channel
    return_code = RETURN_BAD_INDEX;
  }
  return return_code;
}

uint8_t DmfControlBoard::GetPeak(const uint8_t channel,
                               const uint16_t sample_time_ms) {
  peak_ = 128;
  SetPot(POT_AREF,peak_);
  attachInterrupt(channel, PeakExceededWrapper, RISING);
  delay(sample_time_ms);
  detachInterrupt(channel);
  SetPot(POT_AREF,255);
  return peak_;
}

// update the state of all electrodes
void DmfControlBoard::UpdateAllElectrodes() {
  // Each PCA9505 chip has 5 8-bit output registers for a total of 40 outputs
  // per chip. We can have up to 8 of these chips on an I2C bus, which means
  // we can control up to 320 electrodes.
  //   Each register represent 8 electrodes (i.e. the first register on the
  // first PCA9505 chip stores the state of electrodes 0-7, the second register
  // represents electrodes 8-15, etc.).
  uint8_t data = 0;
  for(uint8_t chip=0; chip<NUMBER_OF_ELECTRODES_/40; chip++) {
    for(uint8_t port=0; port<5; port++) {
      data = 0;
      for(uint8_t i=0; i<8; i++) {
        data += (state_of_electrodes_[chip*40+port*8+i]==0)<<i;
      }
      SendI2C(PCA9505_ADDRESS_+chip, PCA9505_OUTPUT_PORT_REGISTER_+port, data);
    }
  }
}

// update the state of single electrode
// Note: Do not use this function in a loop to update all electrodes. If you
//       want to update all electrodes, use the UpdateAllElectrodes function
//       instead because it will be 8x more efficient.
void DmfControlBoard::UpdateElectrode(const uint16_t electrode) {
  uint8_t data = 0;
  uint16_t chip = electrode/40;
  uint8_t port = (electrode-40*chip)/8;

  // We can't update single electrodes; instead we need to update all 8
  // electrodes that share a common output port register. See
  // UpdateAllElectrodes for more details.
  for(uint8_t i=0; i<8; i++) {
    data += (state_of_electrodes_[chip*40+port*8+i]==0)<<i;
  }
  SendI2C(PCA9505_ADDRESS_+chip,
          PCA9505_OUTPUT_PORT_REGISTER_+port,
          data);
}

#else
////////////////////////////////////////////////////////////////////////////////
//
// These functions are only defined on the PC.
//
////////////////////////////////////////////////////////////////////////////////

uint8_t DmfControlBoard::SendCommand(const uint8_t cmd) {
  const char* function_name = "SendCommand()";
  std::ostringstream msg;
  msg << "time since last," << MillisecondsSinceLastCheck();
  RemoteObject::SendCommand(cmd);
  msg << ",ms,returned in," << MillisecondsSinceLastCheck() << ",ms,command,"
      << (int)cmd << ",";
  if(return_code()!=RETURN_OK) {
    msg << "return code," << (int)return_code();
  }
  LogExperiment(msg.str().c_str());
  msg.str("");
  msg << "returned " << (int)return_code();
  LogMessage(msg.str().c_str(), function_name);
  return return_code();
}

string DmfControlBoard::protocol_name() {
  const char* function_name = "protocol_name()";
  LogSeparator();
  LogMessage("send command", function_name);
  if(SendCommand(CMD_GET_PROTOCOL_NAME)==RETURN_OK) {
    return protocol_name_;
  }
  return "";
}

string DmfControlBoard::protocol_version() {
  const char* function_name = "protocol_version()";
  LogSeparator();
  LogMessage("send command", function_name);
  if(SendCommand(CMD_GET_PROTOCOL_VERSION)==RETURN_OK) {
    return protocol_version_;
  }
  return "";
}

string DmfControlBoard::name() {
  const char* function_name = "name()";
  LogSeparator();
  LogMessage("send command", function_name);
  if(SendCommand(CMD_GET_DEVICE_NAME)==RETURN_OK) {
    return name_;
  }
  return "";
}

string DmfControlBoard::version() {
  const char* function_name = "version()";
  LogSeparator();
  LogMessage("send command", function_name);
  if(SendCommand(CMD_GET_DEVICE_VERSION)==RETURN_OK) {
    return version_;
  }
  return "";
}

uint16_t DmfControlBoard::number_of_electrodes() {
  const char* function_name = "number_of_electrodes()";
  LogSeparator();
  LogMessage("send command", function_name);
  if(SendCommand(CMD_GET_NUMBER_OF_ELECTRODES)==RETURN_OK) {
    return state_of_electrodes_.size();
  }
  return 0;
}

vector<uint8_t> DmfControlBoard::state_of_all_electrodes() {
  const char* function_name = "state_of_all_electrodes()";
  LogSeparator();
  LogMessage("send command", function_name);
  if(SendCommand(CMD_GET_STATE_OF_ALL_ELECTRODES)==RETURN_OK) {
    return state_of_electrodes_;
  }
  return std::vector<uint8_t>(); // return an empty vector
};

uint8_t DmfControlBoard::state_of_electrode(const uint16_t electrode) {
  const char* function_name = "state_of_electrode()";
  LogSeparator();
  LogMessage("send command", function_name);
  Serialize(&electrode,sizeof(electrode));
  if(SendCommand(CMD_GET_STATE_OF_ELECTRODE)==RETURN_OK) {
    return state_of_electrodes_[electrode];
  }
  return 0;
};

float DmfControlBoard::sampling_rate() {
  const char* function_name = "sampling_rate()";
  LogSeparator();
  LogMessage("send command", function_name);
  if(SendCommand(CMD_GET_SAMPLING_RATE)==RETURN_OK) {
    return sampling_rate_;
  }
  return 0;
}

uint8_t DmfControlBoard::set_sampling_rate(const uint8_t sampling_rate) {
  const char* function_name = "set_sampling_rate()";
  LogSeparator();
  LogMessage("send command", function_name);
  Serialize(&sampling_rate,sizeof(sampling_rate));
  if(SendCommand(CMD_SET_SAMPLING_RATE)==RETURN_OK) {
    std::ostringstream msg;
    msg << "set sampling rate," << (int)sampling_rate << endl;
    LogExperiment(msg.str().c_str());
  }
  return return_code();
}

float DmfControlBoard::series_resistor(const uint8_t channel) {
  const char* function_name = "series_resistor()";
  LogSeparator();
  LogMessage("send command", function_name);
  Serialize(&channel,sizeof(channel));
  if(SendCommand(CMD_GET_SERIES_RESISTOR)==RETURN_OK) {
    return series_resistor_;
  }
  return 0;
}

uint8_t DmfControlBoard::set_series_resistor(const uint8_t channel,
                                           const uint8_t series_resistor) {
  const char* function_name = "set_series_resistor()";
  LogSeparator();
  LogMessage("send command", function_name);
  Serialize(&channel,sizeof(channel));
  Serialize(&series_resistor,sizeof(series_resistor));
  if(SendCommand(CMD_SET_SERIES_RESISTOR)==RETURN_OK) {
    std::ostringstream msg;
    msg << "set series resistor," << (int)channel
        << (int)series_resistor << endl;
    LogExperiment(msg.str().c_str());
  }
  return return_code();
}

uint8_t DmfControlBoard::set_pot(const uint8_t index, const uint8_t value) {
  const char* function_name = "set_pot()";
  LogSeparator();
  LogMessage("send command", function_name);
  Serialize(&index,sizeof(index));
  Serialize(&value,sizeof(value));
  if(SendCommand(CMD_SET_POT)==RETURN_OK) {
    std::ostringstream msg;
    msg << "set pot," << (int)index
        << (int)value << endl;
    LogExperiment(msg.str().c_str());
  }
  return return_code();
}


uint8_t DmfControlBoard::set_state_of_all_electrodes(const vector<uint8_t> state) {
  const char* function_name = "set_state_of_all_electrodes()";
  LogSeparator();
  LogMessage("send command", function_name);
  Serialize(&state[0],state.size()*sizeof(uint8_t));
  if(SendCommand(CMD_SET_STATE_OF_ALL_ELECTRODES)==RETURN_OK) {
    // check which electrodes have changed state
    vector<uint8_t> on,off;
    for(int i=0; i<state.size()&&i<state_of_electrodes_.size(); i++) {
      if(state[i]!=state_of_electrodes_[i]) {
        if(state[i]==0) {
          off.push_back(i);
        } else {
          on.push_back(i);
        }
      }
    }
    // update state
    state_of_electrodes_=state;

    // log experiment
    std::ostringstream msg;
    msg << "set_state_of_all_electrodes,";
    if(on.size()||off.size()) {
      if(on.size()>0) {
        msg << "Turn on:,";
        for(int i=0; i<on.size(); i++) {
          msg << (int)on[i] << ",";
        }
      }
      if(off.size()>0) {
        msg << "Turn off:,";
        for(int i=0; i<off.size(); i++) {
          msg << (int)off[i] << ",";
        }
      }
    }
    msg << endl;
    LogExperiment(msg.str().c_str());
  }
  return return_code();
}

uint8_t DmfControlBoard::set_state_of_electrode(const uint16_t electrode, const uint8_t state) {
  const char* function_name = "set_state_of_electrode()";
  LogSeparator();
  LogMessage("send command", function_name);
  Serialize(&electrode,sizeof(electrode));
  Serialize(&state,sizeof(state));
  if(SendCommand(CMD_SET_STATE_OF_ELECTRODE)==RETURN_OK) {
    // keep track of the electrode state
    if(electrode+1>state_of_electrodes_.size()) {
      state_of_electrodes_.resize(electrode+1);
    }
    state_of_electrodes_[electrode]=state;

    // log experiment
    std::ostringstream msg;
    msg << "set_state_of_electrode,";
    if(state==0) {
      msg << "Turn off:," << electrode << endl;
    } else {
      msg << "Turn on:," << electrode << endl;
    }
    LogExperiment(msg.str().c_str());
  }
  return return_code();
}

uint8_t DmfControlBoard::set_actuation_voltage(const float v_rms){
  const char* function_name = "set_actuation_voltage()";
  LogSeparator();
  LogMessage("send command", function_name);
// TODO: gain adjustment only has 255 steps, so send a byte instead of fload
  Serialize(&v_rms,sizeof(v_rms));
  if(SendCommand(CMD_SET_ACTUATION_VOLTAGE)==RETURN_OK) {
    std::ostringstream msg;
    msg << "set_actuation_voltage," << v_rms << ",Vrms" << endl;
    LogExperiment(msg.str().c_str());
  }
  return return_code();
}

uint8_t DmfControlBoard::set_actuation_frequency(const float freq_hz) {
  const char* function_name = "set_actuation_frequency()";
  LogSeparator();
  sprintf(log_message_string_,"freq_hz=%.1f",freq_hz);
  LogMessage(log_message_string_, function_name);
  LogMessage("send command", function_name);
  Serialize(&freq_hz,sizeof(freq_hz));
  if(SendCommand(CMD_SET_ACTUATION_FREQUENCY)==RETURN_OK) {
    std::ostringstream msg;
    msg << "set_actuation_frequency," << freq_hz/1000 << ",kHz" << endl;
    LogExperiment(msg.str().c_str());
  }
  return return_code();
}

std::vector<uint16_t> DmfControlBoard::SampleVoltage(
                                        std::vector<uint8_t> ad_channel,
                                        uint16_t n_samples,
                                        uint16_t n_sets,
                                        uint16_t delay_between_sets_ms,
                                        const std::vector<uint8_t> state) {
  const char* function_name = "SampleVoltage()";
  LogSeparator();
  LogMessage("send command", function_name);
  // if we get this far, everything is ok
  Serialize(&n_samples,sizeof(n_samples));
  Serialize(&n_sets,sizeof(n_sets));
  Serialize(&delay_between_sets_ms,sizeof(delay_between_sets_ms));
  uint8_t n_channels = ad_channel.size();
  Serialize(&n_channels,sizeof(n_channels));
  for(uint8_t i=0; i<ad_channel.size(); i++) {
    Serialize(&ad_channel[i],sizeof(ad_channel[i]));
  }
  std::ostringstream msg;
  msg << "SampleVoltage,";

  SerializeElectrodeState(state, msg);

  msg << endl << CSV_INDENT_ << "n_samples,"
      << (int)n_samples << endl << CSV_INDENT_ << "n_sets," << (int)n_sets
      << endl << CSV_INDENT_ << "delay_between_sets_ms,"
      << (int)delay_between_sets_ms << endl;
  if(SendCommand(CMD_SAMPLE_VOLTAGE)==RETURN_OK) {
    for(int i=0; i<ad_channel.size(); i++) {
      for(int j=0; j<n_sets; j++) {
        msg << CSV_INDENT_ << "voltage_buffer_[" << i << "][" << j << "],";
        // calculate the DC bias
        double dc_bias = 0;
        for(int k=0; k<n_samples; k++) {
          dc_bias += (float)voltage_buffer_[j*ad_channel.size()*n_samples+
                                           k*ad_channel.size()+i]
                                           /1024*5/n_samples;
          msg << (float)voltage_buffer_[j*ad_channel.size()*n_samples+
                                       k*ad_channel.size()+i]/1024*5 << ",";
        }
        double v_rms = 0;
        for(int k=0; k<n_samples; k++) {
          v_rms += pow((float)voltage_buffer_[j*ad_channel.size()*n_samples+
                                             k*ad_channel.size()+i]
                                             /1024*5-dc_bias,2)/n_samples;
        }
        v_rms = sqrt(v_rms);
        msg << endl << CSV_INDENT_ << "dc_bias," << dc_bias << endl
            << CSV_INDENT_ << "v_rms," << v_rms << endl;
      }
    }
    LogExperiment(msg.str().c_str());
    return voltage_buffer_;
  }
  return std::vector<uint16_t>(); // return an empty vector
}

std::vector<uint16_t> DmfControlBoard::MeasureImpedance(
                                          uint16_t sampling_time_ms,
                                          uint16_t n_sets,
                                          uint16_t delay_between_sets_ms,
                                          const std::vector<uint8_t> state) {
  const char* function_name = "MeasureImpedance()";
  LogSeparator();
  LogMessage("send command", function_name);
  // if we get this far, everything is ok
  Serialize(&sampling_time_ms,sizeof(sampling_time_ms));
  Serialize(&n_sets,sizeof(n_sets));
  Serialize(&delay_between_sets_ms,sizeof(delay_between_sets_ms));
  std::ostringstream msg;
  msg << "MeasureImpedance,";

  SerializeElectrodeState(state, msg);

  msg << endl << CSV_INDENT_ << "sampling_time_ms," << (int)sampling_time_ms
      << "n_sets," << (int)n_sets << endl << CSV_INDENT_
      << "delay_between_sets_ms," << (int)delay_between_sets_ms << endl;
  if(SendCommand(CMD_MEASURE_IMPEDANCE)==RETURN_OK) {
/*
      for(int j=0; j<n_sets; j++) {
        msg << CSV_INDENT_ << "voltage_buffer_[" << i << "][" << j << "],";
        // calculate the DC bias
        double dc_bias = 0;
        for(int k=0; k<n_samples; k++) {
          dc_bias += (float)voltage_buffer_[j*ad_channel.size()*n_samples+
                                           k*ad_channel.size()+i]
                                           /1024*5/n_samples;
          msg << (float)voltage_buffer_[j*ad_channel.size()*n_samples+
                                       k*ad_channel.size()+i]/1024*5 << ",";
        }
        double v_rms = 0;
        for(int k=0; k<n_samples; k++) {
          v_rms += pow((float)voltage_buffer_[j*ad_channel.size()*n_samples+
                                             k*ad_channel.size()+i]
                                             /1024*5-dc_bias,2)/n_samples;
        }
        v_rms = sqrt(v_rms);
        msg << endl << CSV_INDENT_ << "dc_bias," << dc_bias << endl
            << CSV_INDENT_ << "v_rms," << v_rms << endl;
      }
*/
    LogExperiment(msg.str().c_str());
    return impedance_buffer_;
  }
  return std::vector<uint16_t>(); // return an empty vector
}

uint8_t DmfControlBoard::SetExperimentLogFile(const char* file_name) {
  const char* function_name = "SetExperimentLogFile()";
  if(experiment_log_file_.is_open()) {
    experiment_log_file_.close();
  }
  std::ostringstream msg;
  msg << "file_name=" << file_name;
  LogMessage(msg.str().c_str(), function_name);
  experiment_log_file_name_ = file_name;
  t_last_check_ = boost::posix_time::microsec_clock::universal_time();
  experiment_log_file_.open(experiment_log_file_name_.c_str(), ios::app);
  if(experiment_log_file_.fail()==false) {
    return RETURN_OK;
  } else {
    return RETURN_GENERAL_ERROR;
  }
}

void DmfControlBoard::LogExperiment(const char* msg) {
  if(experiment_log_file_.is_open()) {
    experiment_log_file_ << msg;
    experiment_log_file_.flush();
  }
}

float DmfControlBoard::MillisecondsSinceLastCheck() {
  boost::posix_time::ptime t = t_last_check_;
  t_last_check_ = boost::posix_time::microsec_clock::universal_time();
  return floor(0.5+(float)(boost::posix_time::microsec_clock::universal_time()-t)
         .total_microseconds()/1000);
}

void DmfControlBoard::SerializeElectrodeState(const std::vector<uint8_t> state,
                                            std::ostringstream& msg) {
  // if we're updating the electrode state
  if(state.size()) {
    Serialize(&state[0],state.size()*sizeof(uint8_t));

    // check which electrodes have changed state
    vector<uint8_t> on,off;
    for(int i=0; i<state.size()&&i<state_of_electrodes_.size(); i++) {
      if(state[i]!=state_of_electrodes_[i]) {
        if(state[i]==0) {
          off.push_back(i);
        } else {
          on.push_back(i);
        }
      }
    }
    // update state
    state_of_electrodes_=state;

    if(on.size()||off.size()) {
      if(on.size()>0) {
        msg << "Turn on:,";
        for(int i=0; i<on.size(); i++) {
          msg << (int)on[i] << ",";
        }
      }
      if(off.size()>0) {
        msg << "Turn off:,";
        for(int i=0; i<off.size(); i++) {
          msg << (int)off[i] << ",";
        }
      }
    }
  }
}

#endif // AVR
