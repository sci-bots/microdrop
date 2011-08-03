#ifndef _DMF_CONTROL_BOARD_H_
#define _DMF_CONTROL_BOARD_H_

#ifndef AVR
  #include <iostream>
  #include <fstream>
  #include <string>
  #include <vector>
#endif
#include "RemoteObject.h"

class DmfControlBoard : public RemoteObject {
public:
  static const uint32_t BAUD_RATE = 115200;

  // TODO:
  //  Eventually, all of these variables should defined only on the arduino.
  //  The PC can interogate device using CMD_GET_NUMBER_OF_AD_CHANNELS,
  //  CMD_GET_MAX_SAMPLES
  static const uint8_t NUMBER_OF_AD_CHANNELS = 2;
  static const uint16_t MAX_SAMPLES =
                          (RemoteObject::MAX_PAYLOAD_LENGTH-1)/sizeof(uint16_t);

  //////////////////////////////////////////////////////////////////////////////
  //
  // Commands:
  //
  // Commands are uint8_t and should have the MSB=1 (replies will have MSB=0).
  //
  // Valid commands are in the range 0x80 to 0xFF.
  //
  // The following commands are reserved (they are defined by the
  // RemoteObject class):
  //
  // 0x80 -> CMD_GET_PROTOCOL_NAME
  // 0x81 -> CMD_GET_PROTOCOL_VERSION
  // 0x82 -> CMD_GET_DEVICE_NAME
  // 0x83 -> CMD_GET_MANUFACTURER
  // 0x84 -> CMD_GET_SOFTWARE_VERSION
  // 0x85 -> CMD_GET_HARDWARE_VERSION
  // 0x86 -> CMD_GET_URL
  //
  //////////////////////////////////////////////////////////////////////////////

  // Accessors and mutators
  static const uint8_t CMD_GET_NUMBER_OF_CHANNELS =         0x87;
  static const uint8_t CMD_GET_STATE_OF_ALL_CHANNELS =      0x88;
  static const uint8_t CMD_SET_STATE_OF_ALL_CHANNELS =      0x89;
  static const uint8_t CMD_GET_STATE_OF_CHANNEL =           0x8A;
  static const uint8_t CMD_SET_STATE_OF_CHANNEL =           0x8B;
  static const uint8_t CMD_GET_ACTUATION_WAVEFORM =         0x8C; //TODO
  static const uint8_t CMD_SET_ACTUATION_WAVEFORM =         0x8D; //TODO
  static const uint8_t CMD_GET_ACTUATION_VOLTAGE =          0x8E;
  static const uint8_t CMD_SET_ACTUATION_VOLTAGE =          0x8F;
  static const uint8_t CMD_GET_ACTUATION_FREQUENCY =        0x90;
  static const uint8_t CMD_SET_ACTUATION_FREQUENCY =        0x91;
  static const uint8_t CMD_GET_SAMPLING_RATE =              0x92;
  static const uint8_t CMD_SET_SAMPLING_RATE =              0x93;
  static const uint8_t CMD_GET_SERIES_RESISTOR =            0x94;
  static const uint8_t CMD_SET_SERIES_RESISTOR =            0x95;
  static const uint8_t CMD_GET_POT =                        0x96;
  static const uint8_t CMD_SET_POT =                        0x97;

  // Other commands
  static const uint8_t CMD_SYSTEM_RESET =                   0xB0; //TODO
  static const uint8_t CMD_DEBUG_MESSAGE =                  0xB1; //TODO
  static const uint8_t CMD_DEBUG_ON =                       0xB2; //TODO
  static const uint8_t CMD_SAMPLE_VOLTAGE =                 0xB3;
  static const uint8_t CMD_MEASURE_IMPEDANCE =              0xB4;


  //////////////////////////////////////////////////////////////////////////////
  //
  // Return codes:
  //
  // Return codes are uint8_t.  Some generic return codes are defined by the
  // RemoteObject class.  You may also create custom return codes as long as
  // they are > 0x10.
  //
  //////////////////////////////////////////////////////////////////////////////

  DmfControlBoard();
  ~DmfControlBoard();

// In our case, the PC is the only one sending commands
#ifndef AVR
  // Remote accessors
  virtual std::string protocol_name();
  virtual std::string protocol_version();
  virtual std::string name();
  virtual std::string manufacturer();
  virtual std::string software_version();
  virtual std::string hardware_version();
  virtual std::string url();

  uint16_t number_of_channels();
  std::vector<uint8_t> state_of_all_channels();
  uint8_t state_of_channel(const uint16_t channel);
  float sampling_rate();
  float series_resistor(const uint8_t channel);

  // Remote mutators (return code is from reply packet)
  uint8_t set_state_of_channel(const uint16_t channel, const uint8_t state);
  uint8_t set_state_of_all_channels(const std::vector<uint8_t> state);
  uint8_t set_actuation_voltage(const float v_rms);
  uint8_t set_actuation_frequency(const float freq_hz);
  uint8_t set_sampling_rate(const uint8_t sampling_rate);
  uint8_t set_series_resistor(const uint8_t channel,
                              const uint8_t series_resistor);
  uint8_t set_pot(const uint8_t index, const uint8_t value);

  // other functions
  std::vector<uint16_t> SampleVoltage(
                          std::vector<uint8_t> ad_channel,
                          uint16_t n_samples,
                          uint16_t n_sets,
                          uint16_t delay_between_sets_ms,
                          const std::vector<uint8_t> state);
  std::vector<float> MeasureImpedance(
                          uint16_t sampling_time_ms,
                          uint16_t n_samples,
                          uint16_t delay_between_samples_ms,
                          const std::vector<uint8_t> state);
  uint8_t SetExperimentLogFile(const char* file_name);
  void LogExperiment(const char* message);
#else
  void begin();
  void PeakExceeded();

  // local accessors
  const char* protocol_name() { return PROTOCOL_NAME_; }
  const char* protocol_version() { return PROTOCOL_VERSION_; }
  const char* name() { return NAME_; } //device name
  const char* manufacturer() { return MANUFACTURER_; }
  const char* software_version() { return SOFTWARE_VERSION_; }
  const char* hardware_version() { return HARDWARE_VERSION_; }
  const char* url() { return URL_; }
#endif

private:
  // private static members
  static const char PROTOCOL_NAME_[];
  static const char PROTOCOL_VERSION_[];
  static const char NAME_[];
  static const char MANUFACTURER_[];
  static const char SOFTWARE_VERSION_[];
  static const char HARDWARE_VERSION_[];
  static const char URL_[];
#ifdef AVR
  static const uint8_t AD5204_SLAVE_SELECT_PIN_ = 53; // digital pot

  static const uint8_t POT_AREF_ = 0;
  static const uint8_t POT_VGND_ = 1;
  static const uint8_t POT_WAVEOUT_GAIN_1_ = 2;
  static const uint8_t POT_WAVEOUT_GAIN_2_ = 3;

  static const uint8_t WAVEFORM_SELECT_ = 9;

  static const uint8_t A0_SERIES_RESISTOR_0_ = 13;
  static const uint8_t A1_SERIES_RESISTOR_0_ = 12;
  static const uint8_t A1_SERIES_RESISTOR_1_ = 11;
  static const uint8_t A1_SERIES_RESISTOR_2_ = 10;

  static const float A0_SERIES_RESISTORS_[];
  static const float A1_SERIES_RESISTORS_[];
  static const float SAMPLING_RATES_[];

  // I2C bus
  // =======
  // A4 SDA
  // A5 SCL

  // SPI bus
  // =======
  // D10 SS
  // D11 MOSI
  // D13 SCK

  // PCA9505 (gpio) chip/register addresses
  static const uint8_t PCA9505_ADDRESS_ = 0x20;
  static const uint8_t PCA9505_CONFIG_IO_REGISTER_ = 0x18;
  static const uint8_t PCA9505_OUTPUT_PORT_REGISTER_ = 0x08;

  // LTC6904 (programmable oscillator) chip address
  static const uint8_t LTC6904_ = 0x17;
  static const uint16_t NUMBER_OF_CHANNELS_ = 80;
#else
  static const char CSV_INDENT_[];
#endif

  // private functions
  virtual void ProcessCommand(uint8_t cmd);
  virtual void ProcessReply(uint8_t cmd);

#ifdef AVR
  void UpdateChannel(const uint16_t channel);
  void UpdateAllChannels();
  void SendI2C(uint8_t row, uint8_t cmd, uint8_t data);
  void SendSPI(uint8_t pin, uint8_t address, uint8_t data);
  uint8_t SetPot(uint8_t index, uint8_t value);
  uint8_t SetSeriesResistor(const uint8_t channel,
                            const uint8_t index);
  uint8_t SetAdcPrescaler(const uint8_t index);
  uint8_t GetPeak(const uint8_t channel, const uint16_t sample_time_ms);
#else
  uint8_t SendCommand(const uint8_t cmd);
  float MillisecondsSinceLastCheck();
  void SerializeChannelState(const std::vector<uint8_t> state,
                               std::ostringstream& msg);
#endif

  //private members
#ifdef AVR
  uint8_t state_of_channels_[NUMBER_OF_CHANNELS_];
  uint8_t sampling_rate_index_;
  uint8_t A0_series_resistor_index_;
  uint8_t A1_series_resistor_index_;
  uint8_t peak_;
#else
  uint8_t pot_value_;
  std::string protocol_name_;
  std::string protocol_version_;
  std::string name_;
  std::string manufacturer_;
  std::string software_version_;
  std::string hardware_version_;
  std::string url_;
  std::vector<uint8_t> state_of_channels_;
  std::vector<uint16_t> voltage_buffer_;
  std::vector<float> impedance_buffer_;
  float sampling_rate_;
  float series_resistor_;
  std::string experiment_log_file_name_;
  std::ofstream experiment_log_file_;
  boost::posix_time::ptime t_last_check_;
#endif
};
#endif // _DMF_CONTROL_BOARD_H_

